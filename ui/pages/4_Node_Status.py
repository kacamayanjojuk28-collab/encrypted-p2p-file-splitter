from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_module import load_config
from ui.ui_helpers import app_config_path, node_status, require_authentication, show_user_error


st.set_page_config(page_title="Node Status", layout="wide")
st.title("Node Status")
if not require_authentication():
    st.stop()

try:
    config = load_config(app_config_path(PROJECT_ROOT))
    rows = []

    for node in config.nodes:
        status_info = node_status(node)
        files = status_info["files"]
        rows.append(
            {
                "node_id": node.id,
                "status": status_info["status"],
                "host": node.host,
                "port": node.port,
                "folder": str(node.folder),
                "part_files": ", ".join(status_info["part_files"]) or "-",
                "share_files": ", ".join(status_info["share_files"]) or "-",
                "all_files": ", ".join(files) or "-",
            }
        )

    st.dataframe(rows, use_container_width=True)

    for row in rows:
        status = row["status"]
        label = f"Node {row['node_id']}: {status}"
        if status == "Ready":
            st.success(label)
        elif status == "Empty":
            st.info(label)
        elif status == "Missing files":
            st.warning(label)
        else:
            st.error(label)
except Exception as exc:
    show_user_error("Node status check failed", exc)
