from pathlib import Path

from main import build_parser
from src.config_module import load_config


def test_config_can_be_passed_after_subcommand() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "encrypt",
            "--input",
            "test.bin",
            "--output",
            "workspace",
            "--config",
            "config.docker.json",
        ]
    )

    assert args.command == "encrypt"
    assert args.config == "config.docker.json"


def test_docker_config_uses_service_names() -> None:
    config = load_config(Path("config.docker.json"))

    assert [node.host for node in config.nodes] == ["node-a", "node-b", "node-c"]
    assert [node.port for node in config.nodes] == [8001, 8002, 8003]
