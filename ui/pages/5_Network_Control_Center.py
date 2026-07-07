from __future__ import annotations

import shutil
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.monitoring_module import (
    append_network_event,
    build_connection_matrix,
    check_node_folder_status,
    check_tcp_health,
    inspect_file_distribution,
    load_node_config,
    read_network_events,
)
from src.storage_module import MANIFEST_NAME
from ui.ui_helpers import app_config_path, show_user_error


st.set_page_config(page_title="Network Control Center", layout="wide")
st.title("Network Control Center")

workspace = Path(st.sidebar.text_input("Workspace", value=str(PROJECT_ROOT / "workspace"))).expanduser()
config_path = app_config_path(PROJECT_ROOT)
if st.sidebar.checkbox("Use Docker config", value=config_path.name == "config.docker.json"):
    config_path = PROJECT_ROOT / "config.docker.json"

try:
    nodes = load_node_config(config_path)

    st.caption(f"Config: `{config_path}`")

    st.subheader("Network Topology")
    graph_lines = ["digraph G {", "  rankdir=LR;", "  node [shape=box, style=rounded];"]
    for node in nodes:
        graph_lines.append(f'  {node.id} [label="Node {node.id}\\n{node.host}:{node.port}"];')
    for source in nodes:
        for target in nodes:
            if source.id == target.id:
                continue
            graph_lines.append(
                f'  {source.id} -> {target.id} [label="{target.host}:{target.port}"];'
            )
    graph_lines.append("}")
    st.graphviz_chart("\n".join(graph_lines), use_container_width=True)

    st.subheader("Node Health Panel")
    health_rows = []
    for node in nodes:
        folder_status = check_node_folder_status(node)
        tcp_status = check_tcp_health(node.host, node.port, timeout=1.5)
        append_network_event(
            {
                "event_type": "node_health",
                "source_node": "ui",
                "target_node": node.id,
                "action": "TCP_HEALTH_CHECK",
                "status": "success" if tcp_status["status"] == "Online" else "timeout",
                "message": tcp_status["message"],
                "duration_ms": tcp_status["duration_ms"],
            },
            workspace,
        )
        display_status = tcp_status["status"]
        if display_status != "Online":
            display_status = folder_status["status"]
        health_rows.append(
            {
                "Node ID": node.id,
                "Host": node.host,
                "Port": node.port,
                "Folder path": folder_status["folder"],
                "Folder exists?": folder_status["folder_exists"],
                "Part file exists?": folder_status["part_file_exists"],
                "Key share exists?": folder_status["key_share_exists"],
                "Last modified time": folder_status["last_modified"],
                "TCP": tcp_status["status"],
                "Status": display_status,
            }
        )
    st.dataframe(health_rows, use_container_width=True)

    st.subheader("Connection Matrix")
    matrix = build_connection_matrix(nodes, timeout=1.5)
    matrix_rows = []
    node_ids = [node.id for node in nodes]
    for source_id, targets in matrix.items():
        row = {"Source": source_id}
        row.update({target_id: targets[target_id] for target_id in node_ids})
        matrix_rows.append(row)
        for target_id, status in targets.items():
            if status == "Self":
                continue
            append_network_event(
                {
                    "event_type": "connection_check",
                    "source_node": source_id,
                    "target_node": target_id,
                    "action": "TCP_CONNECT",
                    "status": "success" if status == "OK" else "timeout",
                    "message": status,
                },
                workspace,
            )
    st.dataframe(matrix_rows, use_container_width=True)
    if not any(status == "OK" for row in matrix.values() for status in row.values()):
        st.info("Node servers are not running or are not reachable from this environment.")

    st.subheader("File Distribution Map")
    manifest_path = workspace / MANIFEST_NAME
    if not manifest_path.exists():
        st.warning("No manifest found. Run Encrypt first, then Distribute.")
    distribution_rows = inspect_file_distribution(nodes, manifest_path)
    st.dataframe(distribution_rows, use_container_width=True)
    for row in distribution_rows:
        if row["status"] != "Ready":
            st.warning(f"Node {row['node_id']} distribution status: {row['status']}")

    st.subheader("Live Event Log / Network Events")
    events = read_network_events(workspace, limit=50)
    if events:
        event_types = sorted({str(event.get("event_type")) for event in events if event.get("event_type")})
        statuses = sorted({str(event.get("status")) for event in events if event.get("status")})
        sources = sorted({str(event.get("source_node")) for event in events if event.get("source_node")})
        targets = sorted({str(event.get("target_node")) for event in events if event.get("target_node")})

        cols = st.columns(4)
        event_type_filter = cols[0].selectbox("event_type", ["All", *event_types])
        source_filter = cols[1].selectbox("source_node", ["All", *sources])
        target_filter = cols[2].selectbox("target_node", ["All", *targets])
        status_filter = cols[3].selectbox("status", ["All", *statuses])

        filtered = []
        for event in events:
            if event_type_filter != "All" and event.get("event_type") != event_type_filter:
                continue
            if source_filter != "All" and event.get("source_node") != source_filter:
                continue
            if target_filter != "All" and event.get("target_node") != target_filter:
                continue
            if status_filter != "All" and event.get("status") != status_filter:
                continue
            filtered.append(event)
        st.dataframe(list(reversed(filtered)), use_container_width=True)
    else:
        st.info("No network events yet.")

    st.subheader("Transfer Flow Viewer")
    reconstruct_events = [
        event for event in events if event.get("event_type") in {"reconstruct", "part_transfer", "error"}
    ]
    if reconstruct_events:
        for index, event in enumerate(reconstruct_events[-9:], start=1):
            label = f"{index}. {event.get('message', '')}"
            if event.get("status") == "error":
                st.error(label)
            else:
                st.success(label)
    else:
        st.info("No transfer flow events yet. Run Distribute or Reconstruct first.")

    st.subheader("Docker Awareness")
    docker_rows = [
        {"Item": "Dockerfile", "Exists?": (PROJECT_ROOT / "Dockerfile").exists()},
        {"Item": "docker-compose.yml", "Exists?": (PROJECT_ROOT / "docker-compose.yml").exists()},
        {"Item": "config.docker.json", "Exists?": (PROJECT_ROOT / "config.docker.json").exists()},
    ]
    st.dataframe(docker_rows, use_container_width=True)
    st.write("Expected services: `app`, `node-a`, `node-b`, `node-c`, `ui`")
    if shutil.which("docker") is None:
        st.warning("Docker runtime not available in this environment.")
    else:
        st.success("Docker runtime detected.")
except Exception as exc:
    show_user_error("Network Control Center failed", exc)
