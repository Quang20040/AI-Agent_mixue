"""Real MCP protocol tests with synthetic readers. No production database or credentials."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from src.mcp.postgres_client import PostgresMCPClient
from src.mcp.postgres_server import PostgresReader, create_server


class SyntheticReader:
    def coverage(self):
        return {
            "status": "SUCCESS",
            "first_date": "2026-10-02",
            "last_date": "2026-10-02",
            "days_with_sales": 1,
            "backend": "postgresql_mcp",
            "source_refs": ["mcp:postgresql:store:2132:table:sales_daily"],
        }

    def sales(self, start_date=None, end_date=None):
        return {
            "status": "SUCCESS",
            "total_quantity_sold": 10,
            "total_revenue_vnd": 100000,
            "backend": "postgresql_mcp",
            "target_date": "02/10/2026",
            "source_refs": ["mcp:postgresql:store:2132:table:sales_daily"],
        }


@pytest.mark.asyncio
async def test_mcp_discovery_schema_and_actual_protocol_call():
    server = create_server(SyntheticReader())
    async with Client(server) as client:
        discovery = await client.list_tools()
        assert {tool.name for tool in discovery.tools} == {"get_data_coverage", "get_daily_sales"}
        for tool in discovery.tools:
            assert tool.annotations.read_only_hint
            assert not tool.annotations.destructive_hint
            assert "store_id" not in tool.input_schema.get("properties", {})
        result = await client.call_tool("get_daily_sales", {"start_date": "2026-10-02"})
        assert not result.is_error
        assert result.structured_content["total_quantity_sold"] == 10


@pytest.mark.asyncio
async def test_agent_client_calls_protocol_and_blocks_nonallowlisted_tools():
    client = PostgresMCPClient("2132", transport=create_server(SyntheticReader()))
    assert (await client.call("get_data_coverage"))["backend"] == "postgresql_mcp"
    assert (await client.call("execute_sql", {"sql": "DELETE FROM users"}))["status"] == "MCP_FORBIDDEN"


@pytest.mark.asyncio
async def test_mcp_failures_never_expose_connection_credentials():
    class BrokenReader(SyntheticReader):
        def coverage(self):
            raise RuntimeError("postgresql://private-user:private-password@internal/db")

    result = await PostgresMCPClient("2132", transport=create_server(BrokenReader())).call("get_data_coverage")
    assert result["status"] == "MCP_DATABASE_ERROR"
    assert "private-password" not in json.dumps(result)


@pytest.mark.asyncio
async def test_mcp_timeout_does_not_become_empty_success():
    from mcp.server import MCPServer

    server = MCPServer("Timeout synthetic server")

    @server.tool()
    async def get_data_coverage() -> dict:
        await asyncio.sleep(1)
        return {"status": "SUCCESS"}

    result = await PostgresMCPClient("2132", transport=server, timeout=0.05).call("get_data_coverage")
    assert result["status"] == "MCP_UNAVAILABLE"


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self.rows


class FakeConnection:
    def __init__(self):
        self.commands = []
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def begin(self):
        return self

    def exec_driver_sql(self, sql):
        self.commands.append(sql)

    def execute(self, sql, parameters):
        self.commands.append(str(sql))
        self.params = parameters
        return FakeResult([{"sku_id": "SYN", "sku_name": "Synthetic", "variant": "M", "quantity_sold": 10, "revenue_vnd": 100000}])


def test_postgres_reader_uses_readonly_transaction_bound_store_and_parameters():
    connection = FakeConnection()

    class Engine:
        def connect(self):
            return connection

    reader = PostgresReader(store_id="2132", engine=Engine())
    result = reader.sales("2026-10-02")
    assert result["total_quantity_sold"] == 10
    assert connection.commands[0] == "SET TRANSACTION READ ONLY"
    assert "statement_timeout" in connection.commands[1]
    assert connection.params["store"] == "2132"
    assert ":store" in connection.commands[2] and ":start" in connection.commands[2]
    with pytest.raises(ValueError):
        reader.sales("2026-10-02'; DROP TABLE users;--")
    with pytest.raises(ValueError):
        reader.sales("2026-10-02", "2026-09-01")
    with pytest.raises(ValueError):
        reader.sales("2020-01-01", "2026-10-01")


@pytest.mark.asyncio
async def test_stdio_discovery_and_invalid_arguments_without_database():
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp.postgres_server"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env={
            "STORE_ID": "2132",
            "APP_DEMO_MODE": "false",
            "POSTGRES_MCP_DATABASE_URL": "postgresql://synthetic:synthetic@localhost:5432/unused",
        },
    )
    async with asyncio.timeout(30):
        async with Client(server, read_timeout_seconds=20) as client:
            discovery = await client.list_tools()
            assert {tool.name for tool in discovery.tools} == {"get_data_coverage", "get_daily_sales"}
            result = await client.call_tool("get_daily_sales", {"start_date": "INVALID"})
            assert result.structured_content["status"] == "INVALID_ARGUMENTS"


def test_fixed_stdio_command_and_minimal_environment(monkeypatch):
    monkeypatch.setenv("POSTGRES_MCP_DATABASE_URL", "postgresql://synthetic:synthetic@localhost/unused")
    monkeypatch.setenv("LLM_API_KEY", "MUST_NOT_BE_PASSED")
    parameters = PostgresMCPClient("2132")._parameters()
    assert parameters.command == sys.executable
    assert parameters.args == ["-m", "src.mcp.postgres_server"]
    assert "LLM_API_KEY" not in parameters.env
