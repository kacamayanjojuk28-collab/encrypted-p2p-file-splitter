from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from src.config_module import get_node, load_config
from src.network_module import run_node_server
from src.storage_module import distribute_workspace, encrypt_workspace, reconstruct_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="encrypted-p2p-file-splitter",
        description="Encrypt, split, distribute, and reconstruct files with 3-of-3 key shares.",
    )
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    encrypt_parser = subparsers.add_parser("encrypt", help="Encrypt and split a file")
    encrypt_parser.add_argument("--input", required=True, help="Input file path")
    encrypt_parser.add_argument("--output", required=True, help="Workspace output folder")

    distribute_parser = subparsers.add_parser("distribute", help="Copy parts and shares to nodes")
    distribute_parser.add_argument("--workspace", required=True, help="Workspace folder")

    reconstruct_parser = subparsers.add_parser("reconstruct", help="Rebuild and decrypt a file")
    reconstruct_parser.add_argument("--workspace", required=True, help="Workspace folder")
    reconstruct_parser.add_argument("--output", required=True, help="Restored output file path")

    node_parser = subparsers.add_parser("node", help="Start a simple localhost node server")
    node_parser.add_argument("--id", required=True, help="Node id from config.json, e.g. A")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)

    try:
        if args.command == "encrypt":
            manifest = encrypt_workspace(Path(args.input), Path(args.output), config)
            print(f"Encryption complete. Manifest: {manifest}")
        elif args.command == "distribute":
            distribute_workspace(Path(args.workspace), config)
            print("Distribution complete.")
        elif args.command == "reconstruct":
            reconstruct_workspace(Path(args.workspace), Path(args.output), config)
            print(f"Reconstruction complete. Output: {Path(args.output)}")
        elif args.command == "node":
            node = get_node(config, args.id)
            asyncio.run(run_node_server(node, config.timeout_seconds))
        else:
            parser.error(f"Unknown command: {args.command}")
    except Exception as exc:
        raise SystemExit(f"Error: {exc}") from exc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
