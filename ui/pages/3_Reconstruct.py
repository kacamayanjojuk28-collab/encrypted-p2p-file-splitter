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
from src.storage_module import MANIFEST_NAME, reconstruct_workspace
from ui.ui_helpers import run_with_history, show_user_error


st.set_page_config(page_title="Reconstruct", layout="wide")
st.title("Reconstruct")

config = load_config(PROJECT_ROOT / "config.json")
workspace_text = st.text_input("Workspace", value=str(PROJECT_ROOT / "workspace"))
output_text = st.text_input("Output filename", value=str(PROJECT_ROOT / "restored.bin"))

if st.button("Reconstruct", type="primary"):
    workspace = Path(workspace_text).expanduser()
    try:
        output_path = Path(output_text).expanduser()

        def operation(tracker):
            reconstruct_workspace(
                workspace=workspace,
                output_path=output_path,
                config=config,
                progress=tracker.step,
            )
            tracker.manual_step("Comparing hashes")
            return {
                "input_file": str((workspace / MANIFEST_NAME).resolve()),
                "output_file": str(output_path.resolve()),
            }

        run_with_history(
            workspace=workspace,
            operation_type="reconstruct",
            labels=[
                "Verifying manifest",
                "Reconstructing file",
                "Reconstructing file",
                "Reconstructing file",
                "Comparing hashes",
            ],
            operation=operation,
        )
        manifest = read_json(workspace / MANIFEST_NAME)
        restored_sha256 = sha256_file(output_path)
        original_sha256 = str(manifest["original_sha256"])
        verified = restored_sha256 == original_sha256

        if verified:
            st.success("Reconstruction completed and hash verification passed.")
        else:
            st.error("Reconstruction completed but hash verification failed.")

        st.write(f"Restored file: `{output_path.resolve()}`")
        st.json(
            {
                "hash_verified": verified,
                "original_sha256": original_sha256,
                "restored_sha256": restored_sha256,
            }
        )
    except Exception as exc:
        show_user_error("Reconstruction failed", exc)
