from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_module import get_node, load_config
from src.network_module import request_node_part


async def probe(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    node = get_node(config, args.node)
    destination = Path(args.dest)
    try:
        part_path, share_path = await request_node_part(
            node=node,
            destination_folder=destination,
            timeout_seconds=config.timeout_seconds,
        )
    except Exception as exc:
        if args.expect_failure:
            print(f"Expected network isolation failure: {exc}")
            return 0
        raise

    if args.expect_failure:
        raise SystemExit("Expected network failure, but node request succeeded")
    print(f"Node probe OK: part={part_path} share={share_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Docker node TCP connectivity.")
    parser.add_argument("--config", default="config.docker.json")
    parser.add_argument("--node", default="A")
    parser.add_argument("--dest", default="workspace/network_probe")
    parser.add_argument("--expect-failure", action="store_true")
    args = parser.parse_args()
    return asyncio.run(probe(args))


if __name__ == "__main__":
    raise SystemExit(main())
