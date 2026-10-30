"""Discover the fixed local MCP server; query only when explicitly requested."""

import argparse
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.mcp.postgres_client import PostgresMCPClient
from src.runtime_settings import configured_store_id


async def inspect_server(query):
    from mcp import Client

    connection = PostgresMCPClient(configured_store_id())
    async with asyncio.timeout(30):
        async with Client(connection._parameters(), read_timeout_seconds=20) as client:
            discovery = await client.list_tools()
            print("MCP tools: " + ", ".join(tool.name for tool in discovery.tools))
            if query:
                result = await client.call_tool("get_data_coverage")
                payload = result.structured_content or {}
                payload = payload.get("result", payload)
                print("Coverage status: " + str(payload.get("status", "MCP_ERROR")))
                return payload.get("status") in {"SUCCESS", "NO_DATA"}
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discover PostgreSQL MCP; mặc định không đọc số liệu kinh doanh.")
    parser.add_argument("--query-coverage", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(0 if asyncio.run(inspect_server(args.query_coverage)) else 1)
    except Exception:
        print("Chưa kết nối được MCP. Kiểm tra cấu hình và dependency; không in URL hoặc mật khẩu.")
        raise SystemExit(1)
