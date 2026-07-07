from __future__ import annotations

import json
import socket
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config_module import NodeConfig, load_config
from .crypto_module import read_json
from .integrity_module import sha256_file


EVENT_LOG_NAME = "network_events.jsonl"


def load_node_config(config_path: Path | str) -> list[NodeConfig]:
    """Load node configuration from the selected application config file."""
    return load_config(config_path).nodes


def check_node_folder_status(node: NodeConfig) -> dict[str, Any]:
    """Inspect node folder contents without requiring node servers to be running."""
    try:
        folder_exists = node.folder.exists()
        files = sorted(path.name for path in node.folder.iterdir() if path.is_file()) if folder_exists else []
        part_files = [name for name in files if name.startswith("part_") and name.endswith(".bin")]
        share_files = [
            name for name in files if name.startswith("key_share_") and name.endswith(".json")
        ]
        last_modified = None
        if folder_exists and files:
            last_modified = max(
                datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
                for path in node.folder.iterdir()
                if path.is_file()
            )

        if not folder_exists:
            status = "Error"
        elif not files:
            status = "Empty"
        elif part_files and share_files:
            status = "Ready"
        else:
            status = "Missing files"

        return {
            "node_id": node.id,
            "host": node.host,
            "port": node.port,
            "folder": str(node.folder),
            "folder_exists": folder_exists,
            "part_file_exists": bool(part_files),
            "key_share_exists": bool(share_files),
            "part_files": part_files,
            "key_share_files": share_files,
            "files": files,
            "last_modified": last_modified,
            "status": status,
        }
    except Exception as exc:
        return {
            "node_id": node.id,
            "host": node.host,
            "port": node.port,
            "folder": str(node.folder),
            "folder_exists": False,
            "part_file_exists": False,
            "key_share_exists": False,
            "part_files": [],
            "key_share_files": [],
            "files": [],
            "last_modified": None,
            "status": "Error",
            "error": str(exc),
        }


def check_tcp_health(host: str, port: int, timeout: float = 1.5) -> dict[str, Any]:
    """Check whether a TCP endpoint accepts connections within the timeout."""
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            duration_ms = int((time.perf_counter() - start) * 1000)
            return {"status": "Online", "duration_ms": duration_ms, "message": "Connected"}
    except socket.timeout:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {"status": "Timeout", "duration_ms": duration_ms, "message": "Timed out"}
    except OSError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {"status": "Offline", "duration_ms": duration_ms, "message": str(exc)}


def build_connection_matrix(
    nodes: list[NodeConfig],
    timeout: float = 1.5,
) -> dict[str, dict[str, str]]:
    """Build a source-target connectivity matrix for configured nodes."""
    target_statuses = {
        node.id: check_tcp_health(node.host, node.port, timeout=timeout)["status"]
        for node in nodes
    }
    matrix: dict[str, dict[str, str]] = {}
    for source in nodes:
        matrix[source.id] = {}
        for target in nodes:
            if source.id == target.id:
                matrix[source.id][target.id] = "Self"
            else:
                matrix[source.id][target.id] = "OK" if target_statuses[target.id] == "Online" else target_statuses[target.id]
    return matrix


def inspect_file_distribution(
    nodes: list[NodeConfig],
    manifest_path: Path | str,
) -> list[dict[str, Any]]:
    """Map part/share files to nodes and verify part hashes when manifest exists."""
    manifest_file = Path(manifest_path)
    manifest: dict[str, Any] | None = None
    parts: list[dict[str, Any]] = []
    if manifest_file.exists():
        raw_manifest = read_json(manifest_file)
        if isinstance(raw_manifest, dict):
            manifest = raw_manifest
            parts = list(raw_manifest.get("parts", []))

    rows: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        part_meta = parts[index] if index < len(parts) else {}
        part_name = str(part_meta.get("filename", f"part_{index + 1}.bin"))
        share_name = str(part_meta.get("key_share", f"key_share_{index + 1}.json"))
        part_path = node.folder / part_name
        share_path = node.folder / share_name
        part_exists = part_path.exists()
        share_exists = share_path.exists()

        if manifest is None:
            sha_status = "No manifest found"
        elif not part_exists:
            sha_status = "missing"
        else:
            expected_hash = str(part_meta.get("sha256", ""))
            try:
                sha_status = "valid" if sha256_file(part_path) == expected_hash else "invalid"
            except Exception as exc:
                sha_status = f"error: {exc}"

        if part_exists and share_exists and sha_status in {"valid", "No manifest found"}:
            status = "Ready"
        elif not part_exists and not share_exists:
            status = "Empty"
        else:
            status = "Missing files"

        rows.append(
            {
                "node_id": node.id,
                "part_file": part_name if part_exists else "-",
                "key_share": share_name if share_exists else "-",
                "sha256_status": sha_status,
                "status": status,
                "folder": str(node.folder),
            }
        )
    return rows


def append_network_event(event: dict[str, Any], workspace_path: Path | str) -> None:
    """Append one JSONL event to workspace/network_events.jsonl."""
    workspace = Path(workspace_path)
    workspace.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event.get("event_type", "unknown"),
        "source_node": event.get("source_node"),
        "target_node": event.get("target_node"),
        "action": event.get("action"),
        "status": event.get("status", "success"),
        "message": event.get("message", ""),
        "duration_ms": event.get("duration_ms"),
    }
    with (workspace / EVENT_LOG_NAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_network_events(workspace_path: Path | str, limit: int = 50) -> list[dict[str, Any]]:
    """Read the most recent network events from workspace/network_events.jsonl."""
    event_path = Path(workspace_path) / EVENT_LOG_NAME
    if not event_path.exists():
        return []

    events: list[dict[str, Any]] = []
    with event_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return events[-limit:]
