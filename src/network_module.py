from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from .config_module import NodeConfig


REQUEST_PART = "REQUEST_PART"
SEND_PART = "SEND_PART"
ERROR = "ERROR"
ACK = "ACK"
LOGGER = logging.getLogger(__name__)


async def run_node_server(node: NodeConfig, timeout_seconds: int | float) -> None:
    """Start a localhost node server that sends its part and key share on request."""
    node.folder.mkdir(parents=True, exist_ok=True)

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        try:
            message = await _read_request(reader, timeout_seconds)
            if message.get("type") != REQUEST_PART:
                await _send_message(writer, {"type": ERROR, "message": "Expected REQUEST_PART"})
                return

            part_path = _find_single_file(node.folder, "part_*.bin")
            share_path = _find_single_file(node.folder, "key_share_*.json")
            await _send_message(writer, {"type": ACK, "node_id": node.id})
            await _send_file_message(writer, part_path, timeout_seconds)
            await _send_file_message(writer, share_path, timeout_seconds)
            await _send_message(writer, {"type": ACK, "message": "transfer_complete"})
            LOGGER.info("Node %s served part request to %s", node.id, peer)
        except Exception as exc:
            LOGGER.warning("Node %s request failed: %s", node.id, exc)
            await _send_message(writer, {"type": ERROR, "message": str(exc)})
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, node.host, node.port)
    LOGGER.info("Node %s listening on %s:%s", node.id, node.host, node.port)
    print(f"Node {node.id} listening on {node.host}:{node.port}")
    async with server:
        await server.serve_forever()


async def request_node_part(
    node: NodeConfig,
    destination_folder: Path | str,
    timeout_seconds: int | float,
) -> tuple[Path, Path]:
    """Request one node's part/share pair and store both via .tmp then rename."""
    destination = Path(destination_folder)
    destination.mkdir(parents=True, exist_ok=True)
    part_path: Path | None = None
    share_path: Path | None = None

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(node.host, node.port),
            timeout=timeout_seconds,
        )
        try:
            await _send_message(writer, {"type": REQUEST_PART})
            ack = await _read_json_line(reader, timeout_seconds)
            if ack.get("type") == ERROR:
                raise RuntimeError(str(ack.get("message", "Node returned an error")))
            if ack.get("type") != ACK:
                raise RuntimeError("Node did not acknowledge REQUEST_PART")

            part_path = await _receive_file_message(reader, destination, timeout_seconds)
            share_path = await _receive_file_message(reader, destination, timeout_seconds)
            final_ack = await _read_json_line(reader, timeout_seconds)
            if final_ack.get("type") == ERROR:
                raise RuntimeError(str(final_ack.get("message", "Node returned an error")))
            if final_ack.get("type") != ACK:
                raise RuntimeError("Node transfer did not finish with ACK")
            return part_path, share_path
        finally:
            writer.close()
            await writer.wait_closed()
    except Exception:
        for path in (part_path, share_path):
            if path is not None and path.exists():
                path.unlink()
        for tmp_path in destination.glob("*.tmp"):
            tmp_path.unlink()
        raise


def _find_single_file(folder: Path, pattern: str) -> Path:
    matches = sorted(folder.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No file matching {pattern} found in {folder}")
    if len(matches) > 1:
        raise ValueError(f"Multiple files matching {pattern} found in {folder}")
    return matches[0]


async def _read_request(reader: asyncio.StreamReader, timeout_seconds: int | float) -> dict[str, Any]:
    raw = await asyncio.wait_for(reader.readline(), timeout=timeout_seconds)
    if not raw:
        raise TimeoutError("Client disconnected before sending a request")
    message = raw.decode("utf-8").strip()
    if message == REQUEST_PART:
        return {"type": REQUEST_PART}
    try:
        parsed = json.loads(message)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid node request. Expected JSON or REQUEST_PART") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Invalid node request. Expected a JSON object")
    return parsed


async def _send_file_message(
    writer: asyncio.StreamWriter,
    path: Path,
    timeout_seconds: int | float,
) -> None:
    await _send_message(
        writer,
        {
            "type": SEND_PART,
            "filename": path.name,
            "size": path.stat().st_size,
        },
    )
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            writer.write(chunk)
            await asyncio.wait_for(writer.drain(), timeout=timeout_seconds)


async def _receive_file_message(
    reader: asyncio.StreamReader,
    destination: Path,
    timeout_seconds: int | float,
) -> Path:
    header = await _read_json_line(reader, timeout_seconds)
    if header.get("type") == ERROR:
        raise RuntimeError(str(header.get("message", "Node returned an error")))
    if header.get("type") != SEND_PART:
        raise RuntimeError("Expected SEND_PART message from node")

    filename = Path(str(header["filename"])).name
    remaining = int(header["size"])
    final_path = destination / filename
    tmp_path = final_path.with_name(f"{final_path.name}.tmp")
    try:
        if tmp_path.exists():
            tmp_path.unlink()
        with tmp_path.open("wb") as handle:
            while remaining:
                chunk = await asyncio.wait_for(
                    reader.read(min(1024 * 1024, remaining)),
                    timeout=timeout_seconds,
                )
                if not chunk:
                    raise RuntimeError(f"Connection closed while receiving {filename}")
                handle.write(chunk)
                remaining -= len(chunk)
        tmp_path.replace(final_path)
        return final_path
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


async def _send_message(writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
    writer.write((json.dumps(message) + "\n").encode("utf-8"))
    await writer.drain()


async def _read_json_line(reader: asyncio.StreamReader, timeout_seconds: int | float) -> dict[str, Any]:
    raw = await asyncio.wait_for(reader.readline(), timeout=timeout_seconds)
    if not raw:
        raise TimeoutError("Timed out waiting for node response")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON response from node") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Invalid node response. Expected a JSON object")
    return parsed
