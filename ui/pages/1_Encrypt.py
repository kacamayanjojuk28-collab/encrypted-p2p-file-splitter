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
from ui.ui_helpers import app_config_path, run_with_history, show_user_error


st.set_page_config(page_title="Encrypt", layout="wide")
st.title("Encrypt")

config = load_config(app_config_path(PROJECT_ROOT))
uploaded_file = st.file_uploader("Select a file to encrypt", type=None)
workspace_text = st.text_input("Output workspace", value=str(PROJECT_ROOT / "workspace"))

if st.button("Encrypt", type="primary", disabled=uploaded_file is None):
    workspace = Path(workspace_text).expanduser()
    try:
        def operation(tracker):
            tracker.manual_step("Preparing workspace")
            workspace.mkdir(parents=True, exist_ok=True)
            input_path = workspace / Path(uploaded_file.name).name
            input_path.write_bytes(uploaded_file.getbuffer())
            manifest_path = encrypt_workspace(
                input_path=input_path,
                workspace=workspace,
                config=config,
                progress=tracker.step,
            )
            return {
                "input_file": str(input_path.resolve()),
                "output_file": str(manifest_path.resolve()),
            }

        result = run_with_history(
            workspace=workspace,
            operation_type="encrypt",
            labels=[
                "Preparing workspace",
                "Encrypting file",
                "Splitting file",
                "Writing manifest",
                "Writing manifest",
            ],
            operation=operation,
        )
        manifest_path = Path(str(result["output_file"]))
        manifest = read_json(manifest_path)

        st.success("Encryption completed successfully.")
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
        st.caption(f"Input copy hash: {sha256_file(Path(str(result['input_file'])))}")
    except Exception as exc:
        show_user_error("Encryption failed", exc)
