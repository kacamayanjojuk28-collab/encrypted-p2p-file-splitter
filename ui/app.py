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


def main() -> None:
    st.set_page_config(
        page_title="Encrypted P2P File Splitter",
        layout="wide",
    )

    st.title("Encrypted P2P File Splitter")
    st.write(
        "AES-256-GCM ile dosya şifreleme, Shamir Secret Sharing ile anahtar "
        "parçalama, P2P node dağıtımı ve SHA-256 bütünlük doğrulama."
    )

    config = load_config(PROJECT_ROOT / "config.json")
    default_workspace = PROJECT_ROOT / "workspace"
    manifest_path = default_workspace / MANIFEST_NAME

    crypto_ready = "Ready"
    node_ready = "Ready" if all(node.folder.exists() for node in config.nodes) else "Missing folders"
    manifest_status = "Found" if manifest_path.exists() else "Not found"
    last_operation = st.session_state.get("last_operation", "No operation yet")

    cols = st.columns(4)
    cols[0].metric("Crypto module", crypto_ready)
    cols[1].metric("Node folders", node_ready)
    cols[2].metric("Manifest status", manifest_status)
    cols[3].metric("Last operation", last_operation)

    st.subheader("Current configuration")
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


if __name__ == "__main__":
    main()
