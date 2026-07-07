from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


NONCE_SIZE = 12
TAG_SIZE = 16
MAX_CHUNKS_PER_FILE = 2**64


def encrypt_file_streaming(
    input_path: Path | str,
    encrypted_path: Path | str,
    key: bytes,
    chunk_size: int,
) -> list[dict[str, int | str]]:
    """Encrypt a file without loading it fully into memory.

    Nonces are 96-bit values built from a random 32-bit prefix and a monotonic
    64-bit chunk counter. The counter is checked before every encryption, which
    makes nonce reuse impossible within a single encrypted file.
    """
    source = Path(input_path)
    target = Path(encrypted_path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if len(key) != 32:
        raise ValueError("AES-256 key must be exactly 32 bytes")

    target.parent.mkdir(parents=True, exist_ok=True)
    aesgcm = AESGCM(key)
    nonce_prefix = os.urandom(4)
    chunks: list[dict[str, int | str]] = []

    with source.open("rb") as in_file, target.open("wb") as out_file:
        chunk_index = 0
        while True:
            plaintext = in_file.read(chunk_size)
            if not plaintext:
                break
            if chunk_index >= MAX_CHUNKS_PER_FILE:
                raise ValueError("File has too many chunks to guarantee unique AES-GCM nonces")
            nonce = nonce_prefix + chunk_index.to_bytes(8, "big")
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)
            out_file.write(nonce)
            out_file.write(ciphertext)
            chunks.append(
                {
                    "index": chunk_index,
                    "nonce": nonce.hex(),
                    "plaintext_size": len(plaintext),
                    "ciphertext_size": len(ciphertext),
                    "record_size": NONCE_SIZE + len(ciphertext),
                }
            )
            chunk_index += 1

    return chunks


def decrypt_file_streaming(
    encrypted_path: Path | str,
    output_path: Path | str,
    key: bytes,
    chunks: list[dict[str, int | str]],
) -> None:
    """Decrypt a manifest-described AES-GCM stream to an output file."""
    source = Path(encrypted_path)
    target = Path(output_path)
    if not source.exists():
        raise FileNotFoundError(f"Encrypted file not found: {source}")
    if len(key) != 32:
        raise ValueError("AES-256 key must be exactly 32 bytes")

    target.parent.mkdir(parents=True, exist_ok=True)
    aesgcm = AESGCM(key)
    try:
        with source.open("rb") as in_file, target.open("wb") as out_file:
            for chunk_meta in chunks:
                expected_nonce = bytes.fromhex(str(chunk_meta["nonce"]))
                record_size = int(chunk_meta["record_size"])
                ciphertext_size = record_size - NONCE_SIZE
                nonce = in_file.read(NONCE_SIZE)
                ciphertext = in_file.read(ciphertext_size)
                if len(nonce) != NONCE_SIZE or len(ciphertext) != ciphertext_size:
                    raise ValueError(
                        f"Encrypted data ended unexpectedly at chunk {chunk_meta['index']}"
                    )
                if nonce != expected_nonce:
                    raise ValueError(f"Nonce mismatch at chunk {chunk_meta['index']}")
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                if len(plaintext) != int(chunk_meta["plaintext_size"]):
                    raise ValueError(f"Plaintext size mismatch at chunk {chunk_meta['index']}")
                out_file.write(plaintext)

            extra = in_file.read(1)
            if extra:
                raise ValueError("Encrypted data has trailing bytes not listed in manifest")
    except InvalidTag as exc:
        if target.exists():
            target.unlink()
        raise ValueError(
            "Decryption failed: key shares or encrypted data are invalid"
        ) from exc
    except Exception:
        if target.exists():
            target.unlink()
        raise


def write_json(path: Path | str, data: dict | list) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def read_json(path: Path | str) -> dict | list:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"JSON file not found: {source}")
    with source.open("r", encoding="utf-8") as handle:
        return json.load(handle)
