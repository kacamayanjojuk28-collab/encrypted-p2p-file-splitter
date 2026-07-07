from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .config_module import AppConfig
from .crypto_module import decrypt_file_streaming, encrypt_file_streaming, read_json, write_json
from .integrity_module import sha256_file, verify_sha256
from .shamir_module import reconstruct_key, split_key


MANIFEST_NAME = "parts_manifest.json"
ENCRYPTED_NAME = "encrypted.bin"


def encrypt_workspace(input_path: Path | str, workspace: Path | str, config: AppConfig) -> Path:
    source = Path(input_path)
    work_dir = Path(workspace)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    work_dir.mkdir(parents=True, exist_ok=True)
    encrypted_path = work_dir / ENCRYPTED_NAME
    key = os.urandom(32)
    chunks = encrypt_file_streaming(source, encrypted_path, key, config.chunk_size)
    part_metas = split_file_into_three_parts(encrypted_path, work_dir, config.chunk_size)
    key_shares = split_key(key)

    for idx, share in enumerate(key_shares, start=1):
        write_json(work_dir / f"key_share_{idx}.json", share)

    manifest = {
        "version": 1,
        "algorithm": "AES-256-GCM",
        "chunk_size": config.chunk_size,
        "original_filename": source.name,
        "original_size": source.stat().st_size,
        "encrypted_file": ENCRYPTED_NAME,
        "encrypted_size": encrypted_path.stat().st_size,
        "chunks": chunks,
        "parts": part_metas,
        "nodes": [{"id": node.id, "folder": str(node.folder)} for node in config.nodes],
    }
    manifest_path = work_dir / MANIFEST_NAME
    write_json(manifest_path, manifest)
    return manifest_path


def split_file_into_three_parts(
    encrypted_path: Path | str,
    workspace: Path | str,
    buffer_size: int,
) -> list[dict[str, int | str]]:
    source = Path(encrypted_path)
    if not source.exists():
        raise FileNotFoundError(f"Encrypted file not found: {source}")

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


def distribute_workspace(workspace: Path | str, config: AppConfig) -> None:
    work_dir = Path(workspace)
    manifest = _load_manifest(work_dir)
    parts = manifest["parts"]
    if len(parts) != 3:
        raise ValueError("Manifest must contain exactly 3 file parts")

    for node, part in zip(config.nodes, parts, strict=True):
        node.folder.mkdir(parents=True, exist_ok=True)
        part_source = work_dir / str(part["filename"])
        share_source = work_dir / str(part["key_share"])
        if not part_source.exists():
            raise FileNotFoundError(f"Missing encrypted part before distribute: {part_source}")
        if not share_source.exists():
            raise FileNotFoundError(f"Missing key share before distribute: {share_source}")
        shutil.copy2(part_source, node.folder / part_source.name)
        shutil.copy2(share_source, node.folder / share_source.name)
        shutil.copy2(work_dir / MANIFEST_NAME, node.folder / MANIFEST_NAME)


def reconstruct_workspace(workspace: Path | str, output_path: Path | str, config: AppConfig) -> None:
    work_dir = Path(workspace)
    manifest = _load_manifest(work_dir)
    parts = manifest["parts"]
    if len(parts) != 3:
        raise ValueError("Manifest must contain exactly 3 file parts")

    collected_dir = work_dir / "reconstruct_tmp"
    if collected_dir.exists():
        shutil.rmtree(collected_dir)
    collected_dir.mkdir(parents=True)

    shares: list[dict[str, str | int]] = []
    for node, part in zip(config.nodes, parts, strict=True):
        node_part = node.folder / str(part["filename"])
        node_share = node.folder / str(part["key_share"])
        if not node_part.exists():
            raise FileNotFoundError(f"Missing part for Node_{node.id}: {node_part}")
        if not node_share.exists():
            raise FileNotFoundError(f"Missing key share for Node_{node.id}: {node_share}")
        verify_sha256(node_part, str(part["sha256"]))
        shares.append(read_json(node_share))  # type: ignore[arg-type]

    key = reconstruct_key(shares)
    combined_path = collected_dir / ENCRYPTED_NAME
    with combined_path.open("wb") as out_file:
        for node, part in zip(config.nodes, parts, strict=True):
            with (node.folder / str(part["filename"])).open("rb") as in_file:
                shutil.copyfileobj(in_file, out_file, length=int(manifest["chunk_size"]))

    if combined_path.stat().st_size != int(manifest["encrypted_size"]):
        raise ValueError("Combined encrypted file size does not match manifest")

    decrypt_file_streaming(combined_path, output_path, key, manifest["chunks"])


def _load_manifest(workspace: Path) -> dict:
    manifest_path = workspace / MANIFEST_NAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
