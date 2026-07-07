from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_module import load_config
from src.crypto_module import read_json
from src.monitoring_module import append_network_event
from src.security_module import load_security_config, validate_workspace_path
from src.storage_module import MANIFEST_NAME, distribute_workspace
from ui.ui_helpers import app_config_path, require_authentication, run_with_history, show_user_error


st.set_page_config(page_title="Distribute", layout="wide")
st.title("Distribute")
if not require_authentication():
    st.stop()

config = load_config(app_config_path(PROJECT_ROOT))
security_config = load_security_config(PROJECT_ROOT / "security_config.json")
workspace_text = st.text_input("Workspace", value="workspace")

if st.button("Distribute", type="primary"):
    workspace = Path(workspace_text).expanduser()
    event_workspace = Path("workspace")
    try:
        workspace = validate_workspace_path(workspace, security_config)
        event_workspace = workspace
        def operation(tracker):
            tracker.manual_step("Verifying manifest")
            distribute_workspace(workspace=workspace, config=config, progress=tracker.step)
            return {
                "input_file": str((workspace / MANIFEST_NAME).resolve()),
                "output_file": str(workspace.resolve()),
            }

        run_with_history(
            workspace=workspace,
            operation_type="distribute",
            labels=["Verifying manifest", "Preparing workspace", "Distributing parts"],
            operation=operation,
        )
        manifest = read_json(workspace / MANIFEST_NAME)

        st.success("Distribution completed successfully.")
        rows = []
        for node, part in zip(config.nodes, manifest["parts"], strict=True):
            append_network_event(
                {
                    "event_type": "part_transfer",
                    "source_node": "app",
                    "target_node": node.id,
                    "action": "DISTRIBUTE_PART",
                    "status": "success",
                    "message": f"Part {part['index']} distributed to Node {node.id}",
                },
                workspace,
            )
            rows.append(
                {
                    "mapping": f"Part {part['index']} -> Node {node.id}",
                    "part_file": str(node.folder / str(part["filename"])),
                    "key_share": str(node.folder / str(part["key_share"])),
                }
            )
        st.dataframe(rows, use_container_width=True)
    except Exception as exc:
        append_network_event(
            {
                "event_type": "error",
                "source_node": "app",
                "target_node": None,
                "action": "DISTRIBUTE_PART",
                "status": "error",
                "message": str(exc),
            },
            event_workspace,
        )
        show_user_error("Distribution failed", exc)
