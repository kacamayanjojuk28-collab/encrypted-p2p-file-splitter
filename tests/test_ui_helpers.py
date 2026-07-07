from pathlib import Path

from src.config_module import NodeConfig
from ui.ui_helpers import append_history, load_history, node_status


def test_append_history_creates_operation_history(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    append_history(
        workspace=workspace,
        operation_type="encrypt",
        status="success",
        started_at=0.0,
        input_file="input.bin",
        output_file="parts_manifest.json",
    )

    history = load_history(workspace)
    assert len(history) == 1
    assert history[0]["operation_type"] == "encrypt"
    assert history[0]["status"] == "success"
    assert history[0]["input_file"] == "input.bin"
    assert history[0]["output_file"] == "parts_manifest.json"
    assert history[0]["error_message"] is None


def test_node_status_reports_ready_missing_and_empty(tmp_path: Path) -> None:
    ready_node = NodeConfig("A", "127.0.0.1", 8001, tmp_path / "ready")
    ready_node.folder.mkdir()
    (ready_node.folder / "part_1.bin").write_bytes(b"part")
    (ready_node.folder / "key_share_1.json").write_text("{}", encoding="utf-8")

    missing_node = NodeConfig("B", "127.0.0.1", 8002, tmp_path / "missing")
    missing_node.folder.mkdir()
    (missing_node.folder / "part_2.bin").write_bytes(b"part")

    empty_node = NodeConfig("C", "127.0.0.1", 8003, tmp_path / "empty")

    assert node_status(ready_node)["status"] == "Ready"
    assert node_status(missing_node)["status"] == "Missing files"
    assert node_status(empty_node)["status"] == "Empty"
