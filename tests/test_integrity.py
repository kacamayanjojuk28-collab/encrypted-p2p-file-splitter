from pathlib import Path

import pytest

from src.integrity_module import sha256_file, verify_sha256


def test_verify_sha256_accepts_matching_hash(tmp_path: Path) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(b"abc")
    expected = sha256_file(path)

    verify_sha256(path, expected)


def test_verify_sha256_rejects_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(b"abc")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_sha256(path, "0" * 64)
