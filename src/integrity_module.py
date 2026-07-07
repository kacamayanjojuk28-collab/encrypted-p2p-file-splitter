from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path | str, chunk_size: int = 1024 * 1024) -> str:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found for SHA-256 calculation: {file_path}")

    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path | str, expected_hash: str, chunk_size: int = 1024 * 1024) -> None:
    actual_hash = sha256_file(path, chunk_size=chunk_size)
    if actual_hash != expected_hash:
        raise ValueError(
            f"SHA-256 mismatch for {Path(path)}: expected {expected_hash}, got {actual_hash}"
        )
