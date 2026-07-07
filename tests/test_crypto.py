from pathlib import Path

from src.crypto_module import decrypt_file_streaming, encrypt_file_streaming


def test_encrypt_decrypt_streaming_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "input.bin"
    encrypted = tmp_path / "encrypted.bin"
    restored = tmp_path / "restored.bin"
    source.write_bytes((b"hello world" * 1000) + b"tail")
    key = b"\x01" * 32

    chunks = encrypt_file_streaming(source, encrypted, key, chunk_size=128)
    decrypt_file_streaming(encrypted, restored, key, chunks)

    assert restored.read_bytes() == source.read_bytes()
    assert len({chunk["nonce"] for chunk in chunks}) == len(chunks)
