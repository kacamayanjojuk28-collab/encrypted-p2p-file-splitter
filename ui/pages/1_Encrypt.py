from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_module import load_config
from src.crypto_module import read_json
from src.integrity_module import sha256_file
from src.storage_module import encrypt_workspace


st.set_page_config(page_title="Encrypt", layout="wide")
st.title("Encrypt")

config = load_config(PROJECT_ROOT / "config.json")
uploaded_file = st.file_uploader("Select a file to encrypt", type=None)
workspace_text = st.text_input("Output workspace", value=str(PROJECT_ROOT / "workspace"))

if st.button("Encrypt", type="primary", disabled=uploaded_file is None):
    try:
        workspace = Path(workspace_text).expanduser()
        workspace.mkdir(parents=True, exist_ok=True)
        input_path = workspace / Path(uploaded_file.name).name
        input_path.write_bytes(uploaded_file.getbuffer())

        messages: list[str] = []
        manifest_path = encrypt_workspace(
            input_path=input_path,
            workspace=workspace,
            config=config,
            progress=messages.append,
        )
        manifest = read_json(manifest_path)
        st.session_state["last_operation"] = "Encrypt completed"

        st.success("Encryption completed successfully.")
        for message in messages:
            st.write(message)

        st.metric("Generated parts", len(manifest["parts"]))
        st.write(f"Manifest: `{manifest_path.resolve()}`")
        st.write(f"Original SHA-256: `{manifest['original_sha256']}`")

        st.subheader("Encrypted file")
        st.json(
            {
                "encrypted_file": manifest["encrypted_file"],
                "encrypted_size": manifest["encrypted_size"],
                "chunk_size": manifest["chunk_size"],
                "chunks": len(manifest["chunks"]),
            }
        )

        st.subheader("Parts")
        st.dataframe(
            [
                {
                    "part": part["index"],
                    "filename": part["filename"],
                    "size": part["size"],
                    "sha256": part["sha256"],
                    "key_share": part["key_share"],
                }
                for part in manifest["parts"]
            ],
            use_container_width=True,
        )
        st.caption(f"Input copy hash: {sha256_file(input_path)}")
    except Exception as exc:
        st.error(f"Encryption failed: {exc}")
