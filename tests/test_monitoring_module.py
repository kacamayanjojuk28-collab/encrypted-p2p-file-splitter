from pathlib import Path

from src.config_module import NodeConfig
from src.monitoring_module import (
    append_network_event,
    build_connection_matrix,
    check_node_folder_status,
    inspect_file_distribution,
    load_node_config,
    read_network_events,
)


def test_load_node_config_reads_nodes() -> None:
    nodes = load_node_config(Path("config.json"))

    assert [node.id for node in nodes] == ["A", "B", "C"]


def test_empty_node_folder_returns_empty(tmp_path: Path) -> None:
    node = NodeConfig("A", "127.0.0.1", 8001, tmp_path / "Node_A")
    node.folder.mkdir()

    status = check_node_folder_status(node)

    assert status["status"] == "Empty"
    assert status["folder_exists"] is True


def test_part_and_share_node_returns_ready(tmp_path: Path) -> None:
    node = NodeConfig("A", "127.0.0.1", 8001, tmp_path / "Node_A")
    node.folder.mkdir()
    (node.folder / "part_1.bin").write_bytes(b"part")
    (node.folder / "key_share_1.json").write_text("{}", encoding="utf-8")

    status = check_node_folder_status(node)

    assert status["status"] == "Ready"
    assert status["part_file_exists"] is True
    assert status["key_share_exists"] is True


def test_network_event_append_and_read(tmp_path: Path) -> None:
    append_network_event(
        {
            "event_type": "connection_check",
            "source_node": "A",
            "target_node": "B",
            "action": "TCP_CONNECT",
            "status": "timeout",
            "message": "Timed out",
            "duration_ms": 10,
        },
        tmp_path,
    )

    events = read_network_events(tmp_path, limit=50)

    assert len(events) == 1
    assert events[0]["event_type"] == "connection_check"
    assert events[0]["status"] == "timeout"


def test_connection_matrix_without_tcp_server_is_safe(tmp_path: Path) -> None:
    nodes = [
        NodeConfig("A", "127.0.0.1", 1, tmp_path / "Node_A"),
        NodeConfig("B", "127.0.0.1", 2, tmp_path / "Node_B"),
    ]

    matrix = build_connection_matrix(nodes, timeout=0.1)

    assert matrix["A"]["A"] == "Self"
    assert matrix["B"]["B"] == "Self"
    assert matrix["A"]["B"] in {"Offline", "Timeout", "Error"}


def test_file_distribution_without_manifest_is_safe(tmp_path: Path) -> None:
    nodes = [NodeConfig("A", "127.0.0.1", 8001, tmp_path / "Node_A")]
    nodes[0].folder.mkdir()

    rows = inspect_file_distribution(nodes, tmp_path / "missing_manifest.json")

    assert rows[0]["sha256_status"] == "No manifest found"
    assert rows[0]["status"] == "Empty"
