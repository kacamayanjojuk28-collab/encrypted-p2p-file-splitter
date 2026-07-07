from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .config_module import NodeConfig


async def run_node_server(node: NodeConfig, timeout_seconds: int) -> None:
    node.folder.mkdir(parents=True, exist_ok=True)

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await asyncio.wait_for(reader.readline(), timeout=timeout_seconds)
            message = raw.decode("utf-8").strip()
            if message != "REQUEST_PART":
                await _send_error(writer, "Unsupported message. Expected REQUEST_PART")
                return

            part_path = _find_single_file(node.folder, "part_*.bin")
            share_path = _find_single_file(node.folder, "key_share_*.json")
            payload_header = {
                "status": "ok",
                "part_filename": part_path.name,
                "share_filename": share_path.name,
                "part_size": part_path.stat().st_size,
                "share_size": share_path.stat().st_size,
            }
            writer.write((json.dumps(payload_header) + "\n").encode("utf-8"))
            await writer.drain()
            await _send_file(writer, part_path)
            await _send_file(writer, share_path)
        except Exception as exc:
            await _send_error(writer, str(exc))
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, node.host, node.port)
    async with server:
        print(f"Node {node.id} listening on {node.host}:{node.port}")
        await server.serve_forever()


def _find_single_file(folder: Path, pattern: str) -> Path:
    matches = sorted(folder.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No file matching {pattern} found in {folder}")
    if len(matches) > 1:
        raise ValueError(f"Multiple files matching {pattern} found in {folder}")
    return matches[0]


async def _send_file(writer: asyncio.StreamWriter, path: Path) -> None:
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()


async def _send_error(writer: asyncio.StreamWriter, message: str) -> None:
    writer.write((json.dumps({"status": "error", "message": message}) + "\n").encode("utf-8"))
    await writer.drain()
