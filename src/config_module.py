from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NodeConfig:
    id: str
    host: str
    port: int
    folder: Path


@dataclass(frozen=True)
class AppConfig:
    chunk_size: int
    timeout_seconds: int
    nodes: list[NodeConfig]


def load_config(config_path: Path | str = "config.json") -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    chunk_size = int(raw.get("chunk_size", 0))
    timeout_seconds = int(raw.get("timeout_seconds", 0))
    nodes_raw = raw.get("nodes", [])

    if chunk_size <= 0:
        raise ValueError("config.json must define a positive chunk_size")
    if timeout_seconds <= 0:
        raise ValueError("config.json must define a positive timeout_seconds")
    if len(nodes_raw) != 3:
        raise ValueError("config.json must define exactly 3 nodes for this MVP")

    base_dir = path.resolve().parent
    nodes: list[NodeConfig] = []
    seen_ids: set[str] = set()
    for item in nodes_raw:
        node_id = str(item["id"])
        if node_id in seen_ids:
            raise ValueError(f"Duplicate node id in config.json: {node_id}")
        seen_ids.add(node_id)
        folder = Path(item["folder"])
        if not folder.is_absolute():
            folder = base_dir / folder
        nodes.append(
            NodeConfig(
                id=node_id,
                host=str(item["host"]),
                port=int(item["port"]),
                folder=folder,
            )
        )

    return AppConfig(
        chunk_size=chunk_size,
        timeout_seconds=timeout_seconds,
        nodes=nodes,
    )


def get_node(config: AppConfig, node_id: str) -> NodeConfig:
    for node in config.nodes:
        if node.id == node_id:
            return node
    raise ValueError(f"Unknown node id: {node_id}")
