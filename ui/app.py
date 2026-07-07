from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_module import load_config
from src.crypto_module import read_json
from src.storage_module import MANIFEST_NAME
from ui.ui_helpers import (
    app_config_path,
    last_manifest_value,
    latest_success,
    load_history,
    manifest_status,
    node_health,
    require_authentication,
    show_user_error,
)


def main() -> None:
    st.set_page_config(
        page_title="Encrypted P2P File Splitter",
        layout="wide",
    )

    try:
        st.title("Encrypted P2P File Splitter")
        if not require_authentication():
            return
        st.write(
            "AES-256-GCM file encryption, Shamir Secret Sharing key splitting, "
            "local node distribution, and SHA-256 integrity verification."
        )

        config = load_config(app_config_path(PROJECT_ROOT))
        default_workspace = PROJECT_ROOT / "workspace"
        manifest_path = default_workspace / MANIFEST_NAME
        history = load_history(default_workspace)
        last_operation = history[-1] if history else {}

        st.subheader("Project Dashboard")
        cols = st.columns(5)
        cols[0].metric(
            "Last encrypted file",
            latest_success(history, "encrypt", "input_file")
            or last_manifest_value(default_workspace, "original_filename"),
        )
        cols[1].metric(
            "Last reconstructed file",
            latest_success(history, "reconstruct", "output_file"),
        )
        cols[2].metric("Node health", node_health(config))
        cols[3].metric("Manifest status", manifest_status(default_workspace))
        cols[4].metric(
            "Last operation result",
            str(last_operation.get("status", "No operation yet")),
        )

        if history:
            st.subheader("Recent Operations")
            st.dataframe(list(reversed(history[-5:])), use_container_width=True)
        else:
            st.info("No operation history found yet. Run an Encrypt operation to create it.")

        st.subheader("Network Observability")
        st.page_link(
            "pages/5_Network_Control_Center.py",
            label="Open Network Control Center",
        )

        st.subheader("Current Configuration")
        st.json(
            {
                "chunk_size": config.chunk_size,
                "timeout_seconds": config.timeout_seconds,
                "threshold": config.threshold,
                "nodes": [
                    {
                        "id": node.id,
                        "host": node.host,
                        "port": node.port,
                        "folder": str(node.folder),
                    }
                    for node in config.nodes
                ],
            }
        )

        if manifest_path.exists():
            with st.expander("Default workspace manifest"):
                st.json(read_json(manifest_path))

        st.info("Run with: streamlit run ui/app.py")
    except Exception as exc:
        show_user_error("Dashboard failed", exc)


if __name__ == "__main__":
    main()
