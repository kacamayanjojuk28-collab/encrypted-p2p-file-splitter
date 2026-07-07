from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_module import load_config
from src.storage_module import distribute_workspace, encrypt_workspace, reconstruct_workspace


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Docker E2E file workflow.")
    parser.add_argument("--config", default="config.docker.json")
    args = parser.parse_args()

    config = load_config(args.config)
    workspace = Path("workspace")
    source = workspace / "docker_test.bin"
    restored = workspace / "docker_restored.bin"
    workspace.mkdir(parents=True, exist_ok=True)
    source.write_bytes(bytes(range(256)) * 8)

    encrypt_workspace(source, workspace, config)
    distribute_workspace(workspace, config)
    reconstruct_workspace(workspace, restored, config)

    source_hash = sha256_file(source)
    restored_hash = sha256_file(restored)
    if source_hash != restored_hash:
        raise SystemExit(
            f"Docker E2E hash mismatch: source={source_hash} restored={restored_hash}"
        )
    print(f"Docker E2E OK: {source_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
