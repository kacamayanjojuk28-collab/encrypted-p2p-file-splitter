from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .config_module import AppConfig
from .crypto_module import (
    add_manifest_hmac,
    decrypt_file_streaming,
    encrypt_file_streaming,
    read_json,
    verify_manifest_hmac,
    write_json,
)
from .integrity_module import sha256_file, verify_sha256
from .shamir_module import reconstruct_key, split_key


MANIFEST_NAME = "parts_manifest.json"
ENCRYPTED_NAME = "encrypted.bin"
ProgressCallback = Callable[[str], None]
LOGGER = logging.getLogger(__name__)


def encrypt_workspace(
    input_path: Path | str,
    workspace: Path | str,
    config: AppConfig,
    progress: ProgressCallback | None = None,
) -> Path:
    """Encrypt an input file, split encrypted data, and write manifest metadata."""
    source = Path(input_path)
    work_dir = Path(workspace)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source.resolve()}")

    work_dir.mkdir(parents=True, exist_ok=True)
    encrypted_path = work_dir / ENCRYPTED_NAME
    key = os.urandom(32)
    _notify(progress, "[1/4] Encrypting file...")
    chunks = encrypt_file_streaming(source, encrypted_path, key, config.chunk_size)
    _notify(progress, "[2/4] Splitting encrypted file...")
    part_metas = split_file_into_three_parts(encrypted_path, work_dir, config.chunk_size)
    _notify(progress, "[3/4] Creating key shares...")
    key_shares = split_key(key)

    for idx, share in enumerate(key_shares, start=1):
        write_json(work_dir / f"key_share_{idx}.json", share)

    _notify(progress, "[4/4] Writing manifest...")
    manifest = {
        "version": 1,
        "algorithm": "AES-256-GCM",
        "created_at": datetime.now(UTC).isoformat(),
        "chunk_size": config.chunk_size,
        "threshold": config.threshold,
        "original_filename": source.name,
        "original_size": source.stat().st_size,
        "original_sha256": sha256_file(source),
        "encrypted_file": ENCRYPTED_NAME,
        "encrypted_size": encrypted_path.stat().st_size,
        "chunks": chunks,
        "parts": part_metas,
        "nodes": [{"id": node.id, "folder": str(node.folder)} for node in config.nodes],
    }
    manifest = add_manifest_hmac(manifest, key)
    manifest_path = work_dir / MANIFEST_NAME
    validate_manifest(manifest)
    write_json(manifest_path, manifest)
    LOGGER.info("Encryption workspace created at %s", work_dir.resolve())
    return manifest_path


def split_file_into_three_parts(
    encrypted_path: Path | str,
    workspace: Path | str,
    buffer_size: int,
) -> list[dict[str, int | str]]:
    """Split encrypted data into exactly three contiguous file parts."""
    source = Path(encrypted_path)
    if not source.exists():
        raise FileNotFoundError(f"Encrypted file not found: {source.resolve()}")

    work_dir = Path(workspace)
    total_size = source.stat().st_size
    base_size = total_size // 3
    remainder = total_size % 3
    part_sizes = [base_size + (1 if index < remainder else 0) for index in range(3)]

    parts: list[dict[str, int | str]] = []
    with source.open("rb") as in_file:
        for index, size in enumerate(part_sizes, start=1):
            part_name = f"part_{index}.bin"
            part_path = work_dir / part_name
            remaining = size
            with part_path.open("wb") as out_file:
                while remaining:
                    chunk = in_file.read(min(buffer_size, remaining))
                    if not chunk:
                        raise ValueError(f"Encrypted file ended while writing {part_name}")
                    out_file.write(chunk)
                    remaining -= len(chunk)
            parts.append(
                {
                    "index": index,
                    "filename": part_name,
                    "size": size,
                    "sha256": sha256_file(part_path),
                    "key_share": f"key_share_{index}.json",
                }
            )
    return parts


def distribute_workspace(
    workspace: Path | str,
    config: AppConfig,
    progress: ProgressCallback | None = None,
) -> None:
    """Atomically copy file parts and key shares into configured node folders."""
    work_dir = Path(workspace)
    manifest = _load_manifest(work_dir)
    validate_manifest(manifest)
    parts = manifest["parts"]

    _notify(progress, "[1/2] Validating workspace files...")
    for part in parts:
        part_source = work_dir / str(part["filename"])
        share_source = work_dir / str(part["key_share"])
        if not part_source.exists():
            raise FileNotFoundError(f"Cannot distribute: missing encrypted part {part_source}")
        if not share_source.exists():
            raise FileNotFoundError(f"Cannot distribute: missing key share {share_source}")
        verify_sha256(part_source, str(part["sha256"]))

    _notify(progress, "[2/2] Distributing parts to node folders...")
    for node, part in zip(config.nodes, parts, strict=True):
        node.folder.mkdir(parents=True, exist_ok=True)
        part_source = work_dir / str(part["filename"])
        share_source = work_dir / str(part["key_share"])
        _copy_atomic(part_source, node.folder / part_source.name)
        _copy_atomic(share_source, node.folder / share_source.name)
        _copy_atomic(work_dir / MANIFEST_NAME, node.folder / MANIFEST_NAME)
    LOGGER.info("Workspace distributed to %d node folders", len(config.nodes))


def reconstruct_workspace(
    workspace: Path | str,
    output_path: Path | str,
    config: AppConfig,
    progress: ProgressCallback | None = None,
) -> None:
    """Validate node data, rebuild encrypted bytes, and decrypt the output file."""
    work_dir = Path(workspace)
    _notify(progress, "[1/4] Validating manifest...")
    manifest = _load_manifest(work_dir)
    validate_manifest(manifest, require_hmac=False)
    parts = manifest["parts"]

    collected_dir = work_dir / "reconstruct_tmp"
    if collected_dir.exists():
        shutil.rmtree(collected_dir)
    collected_dir.mkdir(parents=True)

    _notify(progress, "[2/4] Checking node parts and key shares...")
    shares: list[dict[str, str | int]] = []
    for node, part in zip(config.nodes, parts, strict=True):
        node_part = node.folder / str(part["filename"])
        node_share = node.folder / str(part["key_share"])
        if not node_part.exists():
            raise FileNotFoundError(f"Missing part for Node_{node.id}: {node_part.resolve()}")
        if not node_share.exists():
            raise FileNotFoundError(f"Missing key share for Node_{node.id}: {node_share.resolve()}")
        if node_part.stat().st_size != int(part["size"]):
            raise ValueError(
                f"Size mismatch for Node_{node.id} part {node_part.name}: "
                f"expected {part['size']} bytes, got {node_part.stat().st_size}"
            )
        verify_sha256(node_part, str(part["sha256"]))
        shares.append(read_json(node_share))  # type: ignore[arg-type]

    key = reconstruct_key(shares)
    verify_manifest_hmac(manifest, key)
    combined_path = collected_dir / ENCRYPTED_NAME
    _notify(progress, "[3/4] Reassembling encrypted file...")
    with combined_path.open("wb") as out_file:
        for node, part in zip(config.nodes, parts, strict=True):
            with (node.folder / str(part["filename"])).open("rb") as in_file:
                shutil.copyfileobj(in_file, out_file, length=int(manifest["chunk_size"]))

    if combined_path.stat().st_size != int(manifest["encrypted_size"]):
        raise ValueError("Combined encrypted file size does not match manifest")

    _notify(progress, "[4/4] Decrypting output file...")
    decrypt_file_streaming(combined_path, output_path, key, manifest["chunks"])
    LOGGER.info("Reconstructed output written to %s", Path(output_path).resolve())


def validate_manifest(manifest: dict, require_hmac: bool = True) -> None:
    """Validate manifest shape before distribution or reconstruction starts."""
    required_fields = {
        "version",
        "algorithm",
        "created_at",
        "chunk_size",
        "threshold",
        "original_filename",
        "original_size",
        "original_sha256",
        "encrypted_file",
        "encrypted_size",
        "chunks",
        "parts",
    }
    missing = sorted(required_fields - set(manifest))
    if missing:
        raise ValueError(f"Manifest is missing required field(s): {', '.join(missing)}")
    if manifest["algorithm"] != "AES-256-GCM":
        raise ValueError("Manifest algorithm must be AES-256-GCM")
    if int(manifest["threshold"]) != 3:
        raise ValueError("Manifest threshold must be 3 for this MVP")
    if int(manifest["chunk_size"]) <= 0:
        raise ValueError("Manifest chunk_size must be positive")
    if int(manifest["original_size"]) < 0:
        raise ValueError("Manifest original_size cannot be negative")
    if int(manifest["encrypted_size"]) <= 0:
        raise ValueError("Manifest encrypted_size must be positive")
    manifest_hmac = manifest.get("manifest_hmac")
    if require_hmac and manifest_hmac is None:
        raise ValueError("Manifest is missing required field(s): manifest_hmac")
    if manifest_hmac is not None and len(str(manifest_hmac)) != 64:
        raise ValueError("Manifest manifest_hmac must be a SHA-256 HMAC hex digest")

    parts = manifest["parts"]
    if not isinstance(parts, list) or len(parts) != 3:
        raise ValueError("Manifest must contain exactly 3 file parts")
    for expected_index, part in enumerate(parts, start=1):
        for field in ("index", "filename", "size", "sha256", "key_share"):
            if field not in part:
                raise ValueError(f"Manifest part {expected_index} is missing field: {field}")
        if int(part["index"]) != expected_index:
            raise ValueError("Manifest parts must be ordered with indexes 1, 2, 3")
        if int(part["size"]) < 0:
            raise ValueError(f"Manifest part {expected_index} has a negative size")
        if len(str(part["sha256"])) != 64:
            raise ValueError(f"Manifest part {expected_index} has an invalid SHA-256 hash")

    chunks = manifest["chunks"]
    if not isinstance(chunks, list):
        raise ValueError("Manifest chunks must be a list")
    seen_nonces: set[str] = set()
    for expected_index, chunk in enumerate(chunks):
        for field in ("index", "nonce", "plaintext_size", "ciphertext_size", "record_size"):
            if field not in chunk:
                raise ValueError(f"Manifest chunk {expected_index} is missing field: {field}")
        if int(chunk["index"]) != expected_index:
            raise ValueError("Manifest chunks must be ordered from index 0")
        nonce = str(chunk["nonce"])
        if len(nonce) != 24:
            raise ValueError(f"Manifest chunk {expected_index} has an invalid nonce length")
        if nonce in seen_nonces:
            raise ValueError(f"Manifest contains duplicate nonce at chunk {expected_index}")
        seen_nonces.add(nonce)


def _load_manifest(workspace: Path) -> dict:
    manifest_path = workspace / MANIFEST_NAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _copy_atomic(source: Path, destination: Path) -> None:
    tmp_path = destination.with_name(f"{destination.name}.tmp")
    try:
        if tmp_path.exists():
            tmp_path.unlink()
        shutil.copy2(source, tmp_path)
        tmp_path.replace(destination)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _notify(progress: ProgressCallback | None, message: str) -> None:
    LOGGER.info(message)
    if progress is not None:
        progress(message)
