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
from src.monitoring_module import append_network_event
from src.security_module import (
    load_security_config,
    validate_output_file_path,
    validate_workspace_path,
)
from src.storage_module import MANIFEST_NAME, reconstruct_workspace
from ui.ui_helpers import app_config_path, require_authentication, run_with_history, show_user_error


st.set_page_config(page_title="Reconstruct", layout="wide")
st.title("Reconstruct")
if not require_authentication():
    st.stop()

config = load_config(app_config_path(PROJECT_ROOT))
security_config = load_security_config(PROJECT_ROOT / "security_config.json")
workspace_text = st.text_input("Workspace", value="workspace")
output_text = st.text_input("Output filename", value="output/restored.bin")

if st.button("Reconstruct", type="primary"):
    workspace = Path(workspace_text).expanduser()
    event_workspace = Path("workspace")
    try:
        workspace = validate_workspace_path(workspace, security_config)
        event_workspace = workspace
        output_path = validate_output_file_path(Path(output_text).expanduser(), security_config)

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

        flow_messages = [
            "Manifest loaded",
            "Node A part detected",
            "Node B part detected",
            "Node C part detected",
            "Key shares reconstructed",
            "Manifest HMAC verified",
            "Parts joined",
            "File decrypted",
            "SHA-256 matched" if verified else "SHA-256 mismatch",
        ]
        for message in flow_messages:
            append_network_event(
                {
                    "event_type": "reconstruct",
                    "source_node": "app",
                    "target_node": None,
                    "action": "RECONSTRUCT",
                    "status": "success" if verified else "error",
                    "message": message,
                },
                workspace,
            )

        st.write(f"Restored file: `{output_path.resolve()}`")
        st.json(
            {
                "hash_verified": verified,
                "original_sha256": original_sha256,
                "restored_sha256": restored_sha256,
            }
        )
    except Exception as exc:
        append_network_event(
            {
                "event_type": "error",
                "source_node": "app",
                "target_node": None,
                "action": "RECONSTRUCT",
                "status": "error",
                "message": str(exc),
            },
            event_workspace,
        )
        show_user_error("Reconstruction failed", exc)
