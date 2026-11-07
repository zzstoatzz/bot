import os
import sys

import pytest
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import WrapperToolset

from bot.config import settings
from bot.core.mcp_tools import _mcp_origin, build_toolsets


@pytest.mark.parametrize("fail", [False, True])
async def test_fresh_lexidraw_toolsets_release_their_subprocesses(
    tmp_path, monkeypatch, fail
):
    pid_file = tmp_path / "pid"
    server = tmp_path / "server.py"
    server.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "from fastmcp import FastMCP\n"
        f"Path({str(pid_file)!r}).write_text(str(os.getpid()))\n"
        "FastMCP('lifecycle').run(transport='stdio')\n"
    )
    monkeypatch.setattr(settings, "lexidraw_mcp_path", str(server))
    for _ in range(3):
        toolset = next(
            ts for ts in build_toolsets("context-budget") if _mcp_origin(ts) == "lexidraw"
        )
        while isinstance(toolset, WrapperToolset):
            toolset = toolset.wrapped
        assert isinstance(toolset, MCPToolset)
        transport = toolset.client.transport
        assert isinstance(transport, StdioTransport)
        transport.command = sys.executable
        transport.args = [str(server)]
        transport.env = {}
        try:
            try:
                async with toolset:
                    assert await toolset.list_tools() == []
                    pid = int(pid_file.read_text())
                    os.kill(pid, 0)
                    if fail:
                        raise RuntimeError("interrupted listing")
            except RuntimeError as error:
                if str(error) != "interrupted listing":
                    raise
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
        finally:
            await toolset.client.close()
