import json
import random
from pathlib import Path

import pytest

from src.crypto_module import read_json
from src.config_module import AppConfig, NodeConfig
from src.integrity_module import sha256_file
from src.storage_module import distribute_workspace, encrypt_workspace, reconstruct_workspace


def deterministic_bytes(size: int) -> bytes:
    return random.Random(20260707).randbytes(size)


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        chunk_size=64,
        timeout_seconds=5,
        nodes=[
            NodeConfig("A", "127.0.0.1", 8001, tmp_path / "nodes" / "Node_A"),
            NodeConfig("B", "127.0.0.1", 8002, tmp_path / "nodes" / "Node_B"),
            NodeConfig("C", "127.0.0.1", 8003, tmp_path / "nodes" / "Node_C"),
        ],
    )


def test_encrypt_distribute_reconstruct_round_trip(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    source = tmp_path / "test.bin"
    workspace = tmp_path / "workspace"
    restored = tmp_path / "restored.bin"
    source.write_bytes(deterministic_bytes(4096))

    manifest_path = encrypt_workspace(source, workspace, config)
    distribute_workspace(workspace, config)
    reconstruct_workspace(workspace, restored, config)

    manifest = read_json(manifest_path)
    assert manifest["original_filename"] == "test.bin"
    assert manifest["original_size"] == source.stat().st_size
    assert manifest["original_sha256"] == sha256_file(source)
    assert manifest["encrypted_size"] > 0
    assert manifest["created_at"]
    assert manifest["chunk_size"] == config.chunk_size
    assert manifest["threshold"] == 3
    assert len(manifest["parts"]) == 3
    assert sha256_file(restored) == sha256_file(source)


def test_reconstruct_fails_when_part_is_missing(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    source = tmp_path / "test.bin"
    workspace = tmp_path / "workspace"
    source.write_bytes(deterministic_bytes(2048))
    encrypt_workspace(source, workspace, config)
    distribute_workspace(workspace, config)
    (config.nodes[1].folder / "part_2.bin").unlink()

    with pytest.raises(FileNotFoundError, match="Missing part for Node_B"):
        reconstruct_workspace(workspace, tmp_path / "restored.bin", config)


def test_reconstruct_rejects_wrong_hash(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    source = tmp_path / "test.bin"
    workspace = tmp_path / "workspace"
    source.write_bytes(deterministic_bytes(2048))
    encrypt_workspace(source, workspace, config)
    distribute_workspace(workspace, config)
    with (config.nodes[0].folder / "part_1.bin").open("r+b") as handle:
        handle.seek(0)
        handle.write(b"X")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        reconstruct_workspace(workspace, tmp_path / "restored.bin", config)


def test_reconstruct_fails_with_only_two_key_shares(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    source = tmp_path / "test.bin"
    workspace = tmp_path / "workspace"
    source.write_bytes(deterministic_bytes(2048))
    encrypt_workspace(source, workspace, config)
    distribute_workspace(workspace, config)
    (config.nodes[2].folder / "key_share_3.json").unlink()

    with pytest.raises(FileNotFoundError, match="Missing key share for Node_C"):
        reconstruct_workspace(workspace, tmp_path / "restored.bin", config)


def test_reconstruct_rejects_wrong_key_share(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    source = tmp_path / "test.bin"
    workspace = tmp_path / "workspace"
    source.write_bytes(deterministic_bytes(2048))
    encrypt_workspace(source, workspace, config)
    distribute_workspace(workspace, config)

    share_path = config.nodes[2].folder / "key_share_3.json"
    share = json.loads(share_path.read_text(encoding="utf-8"))
    share["y"] = hex(int(share["y"], 16) + 1)
    share_path.write_text(json.dumps(share), encoding="utf-8")

    with pytest.raises(ValueError, match="Decryption failed"):
        reconstruct_workspace(workspace, tmp_path / "restored.bin", config)
