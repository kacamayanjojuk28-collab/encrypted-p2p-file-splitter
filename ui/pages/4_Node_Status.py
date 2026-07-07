from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_module import load_config


st.set_page_config(page_title="Node Status", layout="wide")
st.title("Node Status")

try:
    config = load_config(PROJECT_ROOT / "config.json")
    rows = []
    missing_messages = []

    for node in config.nodes:
        part_files = sorted(node.folder.glob("part_*.bin"))
        share_files = sorted(node.folder.glob("key_share_*.json"))
        has_part = bool(part_files)
        has_share = bool(share_files)
        rows.append(
            {
                "node_id": node.id,
                "host": node.host,
                "port": node.port,
                "folder": str(node.folder),
                "part_present": has_part,
                "share_present": has_share,
            }
        )
        if not has_part or not has_share:
            missing_messages.append(f"Node {node.id} is missing part or key share files.")

    st.dataframe(rows, use_container_width=True)

    if missing_messages:
        for message in missing_messages:
            st.warning(message)
    else:
        st.success("All node folders contain part and key share files.")
except Exception as exc:
    st.error(f"Node status check failed: {exc}")
