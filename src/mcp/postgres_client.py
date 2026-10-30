"""Bounded client for the project's fixed stdio server; no model-controlled command."""

import asyncio
from pathlib import Path
import sys

from src.runtime_settings import setting

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_TOOLS = frozenset({"get_data_coverage", "get_daily_sales"})


def postgres_mcp_enabled():
    return setting("POSTGRES_MCP_ENABLED", "false").lower() == "true"


class PostgresMCPClient:
    def __init__(self, store_id, *, transport=None, timeout=20):
        self.store_id = store_id
        self.transport = transport
        self.timeout = timeout

    def _parameters(self):
        from mcp import StdioServerParameters

        dsn = setting("POSTGRES_MCP_DATABASE_URL")
        if not dsn or not self.store_id:
            raise ValueError("POSTGRES_MCP_NOT_CONFIGURED")
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "src.mcp.postgres_server"],
            cwd=str(ROOT),
            env={"POSTGRES_MCP_DATABASE_URL": dsn, "STORE_ID": self.store_id, "APP_ENV": "production", "APP_DEMO_MODE": "false"},
        )

    async def call(self, name, arguments=None):
        if name not in ALLOWED_TOOLS:
            return {"status": "MCP_FORBIDDEN", "message": "Công cụ MCP không nằm trong danh sách được phép."}
        try:
            from mcp import Client

            async with asyncio.timeout(self.timeout):
                async with Client(self.transport or self._parameters(), read_timeout_seconds=self.timeout) as client:
                    discovery = await client.list_tools()
                    if name not in {tool.name for tool in discovery.tools}:
                        return {"status": "MCP_TOOL_MISSING", "message": "MCP server chưa cung cấp công cụ yêu cầu."}
                    result = await client.call_tool(name, arguments or {})
                    content = result.structured_content
                    # MCP SDK v2 wraps a generic dict return in a result field.
                    if isinstance(content, dict) and isinstance(content.get("result"), dict):
                        content = content["result"]
                    if result.is_error or not isinstance(content, dict) or "status" not in content:
                        return {"status": "MCP_ERROR", "message": "MCP trả kết quả không hợp lệ; chưa có bằng chứng để kết luận."}
                    return content
        except Exception:
            # Never return driver/provider exception text containing a database DSN.
            return {"status": "MCP_UNAVAILABLE", "message": "Chưa kết nối được PostgreSQL MCP. Kiểm tra cấu hình, quyền và thời gian chờ."}

    def call_sync(self, name, arguments=None):
        return asyncio.run(self.call(name, arguments))
