from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import streamlit as st

from src.config_module import AppConfig
from src.crypto_module import read_json, write_json
from src.storage_module import MANIFEST_NAME


LOGGER = logging.getLogger(__name__)
HISTORY_FILE_NAME = "operation_history.json"


def show_user_error(title: str, exc: Exception) -> None:
    """Show a friendly UI error and keep full details in logs."""
    LOGGER.exception("%s: %s", title, exc)
    st.error(f"{title}: {exc}")


def history_path(workspace: Path) -> Path:
    return workspace / HISTORY_FILE_NAME


def load_history(workspace: Path) -> list[dict[str, Any]]:
    path = history_path(workspace)
    if not path.exists():
        return []
    data = read_json(path)
    if not isinstance(data, list):
        LOGGER.warning("Ignoring invalid operation history at %s", path)
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def append_history(
    workspace: Path,
    operation_type: str,
    status: str,
    started_at: float,
    input_file: str | None = None,
    output_file: str | None = None,
    error_message: str | None = None,
) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    history = load_history(workspace)
    history.append(
        {
            "operation_type": operation_type,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
            "input_file": input_file,
            "output_file": output_file,
            "duration_seconds": round(time.perf_counter() - started_at, 3),
            "error_message": error_message,
        }
    )
    write_json(history_path(workspace), history[-100:])


class ProgressTracker:
    def __init__(self, labels: list[str]) -> None:
        self.labels = labels
        self.index = 0
        self.progress_bar = st.progress(0)
        self.status_box = st.status("Ready", expanded=True)

    def step(self, message: str) -> None:
        label = normalize_step_label(message)
        self.index = min(self.index + 1, len(self.labels))
        self.progress_bar.progress(self.index / max(len(self.labels), 1))
        self.status_box.write(label)

    def manual_step(self, label: str) -> None:
        self.step(label)

    def complete(self, label: str = "Done") -> None:
        self.progress_bar.progress(1.0)
        self.status_box.update(label=label, state="complete", expanded=False)

    def fail(self, label: str = "Failed") -> None:
        self.status_box.update(label=label, state="error", expanded=True)


def normalize_step_label(message: str) -> str:
    if "Encrypting" in message:
        return "Encrypting file"
    if "Splitting" in message:
        return "Splitting file"
    if "Writing manifest" in message:
        return "Writing manifest"
    if "Creating key shares" in message:
        return "Writing manifest"
    if "Validating workspace" in message:
        return "Preparing workspace"
    if "Distributing" in message:
        return "Distributing parts"
    if "Validating manifest" in message:
        return "Verifying manifest"
    if "Checking node" in message:
        return "Verifying manifest"
    if "Reassembling" in message:
        return "Reconstructing file"
    if "Decrypting" in message:
        return "Reconstructing file"
    return message


def run_with_history(
    workspace: Path,
    operation_type: str,
    labels: list[str],
    operation: Callable[[ProgressTracker], dict[str, str | None]],
) -> dict[str, str | None]:
    started_at = time.perf_counter()
    tracker = ProgressTracker(labels)
    try:
        result = operation(tracker)
        append_history(
            workspace=workspace,
            operation_type=operation_type,
            status="success",
            started_at=started_at,
            input_file=result.get("input_file"),
            output_file=result.get("output_file"),
            error_message=None,
        )
        tracker.complete()
        st.session_state["last_operation"] = f"{operation_type} success"
        return result
    except Exception as exc:
        append_history(
            workspace=workspace,
            operation_type=operation_type,
            status="error",
            started_at=started_at,
            input_file=None,
            output_file=None,
            error_message=str(exc),
        )
        tracker.fail()
        st.session_state["last_operation"] = f"{operation_type} failed"
        raise


def manifest_status(workspace: Path) -> str:
    manifest_path = workspace / MANIFEST_NAME
    if not manifest_path.exists():
        return "Not found"
    try:
        read_json(manifest_path)
    except Exception:
        return "Invalid"
    return "Found"


def last_manifest_value(workspace: Path, key: str) -> str:
    manifest_path = workspace / MANIFEST_NAME
    if not manifest_path.exists():
        return "-"
    try:
        manifest = read_json(manifest_path)
        return str(manifest.get(key, "-"))
    except Exception:
        return "-"


def node_health(config: AppConfig) -> str:
    statuses = [node_status(node)["status"] for node in config.nodes]
    if all(status == "Ready" for status in statuses):
        return "Ready"
    if all(status == "Empty" for status in statuses):
        return "Empty"
    if any(status == "Error" for status in statuses):
        return "Error"
    return "Missing files"


def node_status(node: Any) -> dict[str, Any]:
    try:
        node.folder.mkdir(parents=True, exist_ok=True)
        files = sorted(path.name for path in node.folder.iterdir() if path.is_file())
        part_files = [name for name in files if name.startswith("part_") and name.endswith(".bin")]
        share_files = [
            name for name in files if name.startswith("key_share_") and name.endswith(".json")
        ]
        if not files:
            status = "Empty"
        elif part_files and share_files:
            status = "Ready"
        else:
            status = "Missing files"
        return {
            "status": status,
            "files": files,
            "part_files": part_files,
            "share_files": share_files,
        }
    except Exception as exc:
        LOGGER.exception("Node status failed for %s", getattr(node, "id", "?"))
        return {
            "status": "Error",
            "files": [],
            "part_files": [],
            "share_files": [],
            "error": str(exc),
        }


def latest_success(history: list[dict[str, Any]], operation_type: str, field: str) -> str:
    for entry in reversed(history):
        if entry.get("operation_type") == operation_type and entry.get("status") == "success":
            value = entry.get(field)
            if value:
                return str(value)
    return ""
