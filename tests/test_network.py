import asyncio
from pathlib import Path

import pytest

from src.config_module import NodeConfig
from src.network_module import request_node_part


def test_request_node_part_times_out_and_cleans_tmp_files(tmp_path: Path) -> None:
    async def slow_handler(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        await reader.readline()
        await asyncio.sleep(0.2)
        writer.close()
        await writer.wait_closed()

    async def run_case() -> None:
        server = await asyncio.start_server(slow_handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        node = NodeConfig("T", "127.0.0.1", port, tmp_path / "node")
        destination = tmp_path / "download"

        try:
            with pytest.raises(TimeoutError):
                await request_node_part(node, destination, timeout_seconds=0.05)
            assert list(destination.glob("*.tmp")) == []
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_case())
