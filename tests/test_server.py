"""hypermesh_mcp_server.py 冒烟测试：验证模块可导入且工具已注册。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hypermesh_mcp_server as server  # noqa: E402


def test_module_imports():
    assert hasattr(server, "mcp")
    assert hasattr(server, "APP_NAME")


def test_tools_registered():
    tools = server.mcp._tool_manager._tools if hasattr(
        server.mcp, "_tool_manager"
    ) else {}
    assert len(tools) > 0, "no MCP tools registered"


def test_known_tool_names():
    tools = server.mcp._tool_manager._tools if hasattr(
        server.mcp, "_tool_manager"
    ) else {}
    names = set(tools.keys())
    assert "convert_stp_to_hm" in names, f"expected convert_stp_to_hm, got: {sorted(names)}"