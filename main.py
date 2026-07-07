from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from src.config_module import get_node, load_config
from src.network_module import run_node_server
from src.storage_module import distribute_workspace, encrypt_workspace, reconstruct_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="encrypted-p2p-file-splitter",
        description=(
            "Encrypt files with AES-256-GCM, split encrypted output into 3 parts, "
            "distribute parts to local node folders, and reconstruct the original file."
        ),
    )
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable informational logs for troubleshooting.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    encrypt_parser = subparsers.add_parser(
        "encrypt",
        help="Encrypt an input file, split encrypted data, and create key shares.",
    )
    encrypt_parser.add_argument("--input", required=True, help="Path to the file to encrypt.")
    encrypt_parser.add_argument(
        "--output",
        required=True,
        help="Workspace folder where encrypted parts, key shares, and manifest are written.",
    )
    encrypt_parser.add_argument(
        "--config",
        default=argparse.SUPPRESS,
        help="Path to config.json. Can also be passed before the command.",
    )

    distribute_parser = subparsers.add_parser(
        "distribute",
        help="Validate workspace files and copy each part/share pair to its node folder.",
    )
    distribute_parser.add_argument(
        "--workspace",
        required=True,
        help="Workspace folder created by the encrypt command.",
    )
    distribute_parser.add_argument(
        "--config",
        default=argparse.SUPPRESS,
        help="Path to config.json. Can also be passed before the command.",
    )

    reconstruct_parser = subparsers.add_parser(
        "reconstruct",
        help="Validate node data, reassemble encrypted bytes, and decrypt the restored file.",
    )
    reconstruct_parser.add_argument(
        "--workspace",
        required=True,
        help="Workspace folder containing parts_manifest.json.",
    )
    reconstruct_parser.add_argument(
        "--output",
        required=True,
        help="Path where the restored plaintext file will be written.",
    )
    reconstruct_parser.add_argument(
        "--config",
        default=argparse.SUPPRESS,
        help="Path to config.json. Can also be passed before the command.",
    )

    node_parser = subparsers.add_parser(
        "node",
        help="Start a localhost TCP server for one configured node.",
    )
    node_parser.add_argument("--id", required=True, help="Node id from config.json, e.g. A.")
    node_parser.add_argument(
        "--config",
        default=argparse.SUPPRESS,
        help="Path to config.json. Can also be passed before the command.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    config = load_config(args.config)

    try:
        if args.command == "encrypt":
            workspace = Path(args.output)
            manifest = encrypt_workspace(Path(args.input), workspace, config, progress=print)
            print("Done.")
            print(f"Workspace: {workspace.resolve()}")
            print(f"Manifest: {manifest.resolve()}")
        elif args.command == "distribute":
            distribute_workspace(Path(args.workspace), config, progress=print)
            print("Done.")
            for node in config.nodes:
                print(f"Node {node.id}: {node.folder.resolve()}")
        elif args.command == "reconstruct":
            output = Path(args.output)
            reconstruct_workspace(Path(args.workspace), output, config, progress=print)
            print("Done.")
            print(f"Output: {output.resolve()}")
        elif args.command == "node":
            node = get_node(config, args.id)
            print(f"Starting Node {node.id} with timeout={config.timeout_seconds}s")
            asyncio.run(run_node_server(node, config.timeout_seconds))
        else:
            parser.error(f"Unknown command: {args.command}")
    except Exception as exc:
        raise SystemExit(f"Error: {exc}") from exc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
