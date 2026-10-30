"""Read-only PostgreSQL MCP server, launched over stdio by a trusted host.

No arbitrary SQL, credentials, table names, commands or tenant identifiers are
accepted from tool arguments. STORE_ID and the read-only DSN are server settings.
"""

from datetime import date, timedelta
import os

from mcp import types
from mcp.server import MCPServer


class PostgresReader:
    def __init__(self, dsn=None, store_id=None, engine=None):
        self.dsn = dsn or os.environ.get("POSTGRES_MCP_DATABASE_URL", "")
        self.store_id = store_id or os.environ.get("STORE_ID", "")
        self._engine = engine

    def read(self, statement, parameters):
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import make_url

        if not self.store_id:
            raise ValueError("STORE_ID_REQUIRED")
        if self._engine is None:
            url = make_url(self.dsn)
            if url.get_backend_name() != "postgresql":
                raise ValueError("POSTGRESQL_REQUIRED")
            if url.drivername == "postgresql":
                url = url.set(drivername="postgresql+psycopg2")
            self._engine = create_engine(url, connect_args={"connect_timeout": 5}, pool_pre_ping=True)
        with self._engine.connect() as connection:
            with connection.begin():
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                connection.exec_driver_sql("SET LOCAL statement_timeout = '5000ms'")
                return [dict(row) for row in connection.execute(text(statement), {**parameters, "store": self.store_id}).mappings()]

    def coverage(self):
        rows = self.read(
            """SELECT MIN(business_date) AS first_date, MAX(business_date) AS last_date,
            COUNT(DISTINCT business_date) AS days_with_sales FROM public.sales_daily WHERE store_id=:store""",
            {},
        )
        row = rows[0]
        return {
            "status": "SUCCESS" if row["first_date"] else "NO_DATA",
            "first_date": str(row["first_date"]) if row["first_date"] else None,
            "last_date": str(row["last_date"]) if row["last_date"] else None,
            "days_with_sales": int(row["days_with_sales"]),
            "backend": "postgresql_mcp",
            "source_refs": [f"mcp:postgresql:store:{self.store_id}:table:sales_daily"],
        }

    def sales(self, start_date=None, end_date=None):
        if end_date and not start_date:
            raise ValueError("START_DATE_REQUIRED")
        if start_date is None:
            coverage = self.coverage()
            if coverage["status"] != "SUCCESS":
                return {"status": "NO_DATA", "message": "Chưa có dữ liệu bán hàng."}
            start = date.fromisoformat(coverage["first_date"])
            end = date.fromisoformat(coverage["last_date"])
        else:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date or start_date)
        if end < start or end - start > timedelta(days=365):
            raise ValueError("INVALID_DATE_RANGE")
        rows = self.read(
            """SELECT s.sku_id, m.sku_name, m.variant,
            SUM(s.quantity_sold) AS quantity_sold, SUM(s.revenue_vnd) AS revenue_vnd
            FROM public.sales_daily s JOIN public.menu_items m ON m.sku_id=s.sku_id
            WHERE s.store_id=:store AND s.business_date BETWEEN :start AND :end
            GROUP BY s.sku_id,m.sku_name,m.variant ORDER BY quantity_sold DESC,s.sku_id LIMIT 500""",
            {"start": start, "end": end},
        )
        if not rows:
            return {"status": "NO_DATA", "message": "Không có dữ liệu bán hàng trong khoảng ngày yêu cầu."}
        if len(rows) >= 500:
            return {"status": "RESULT_LIMIT", "message": "Danh mục vượt giới hạn tra cứu; chưa tổng hợp để tránh trả thiếu số liệu."}
        items = [{**row, "quantity_sold": int(row["quantity_sold"]), "revenue_vnd": int(row["revenue_vnd"])} for row in rows]
        return {
            "status": "SUCCESS",
            "backend": "postgresql_mcp",
            "is_single_day": start == end,
            "target_date": start.strftime("%d/%m/%Y") if start == end else None,
            "period": start.strftime("%d/%m/%Y") if start == end else f"{start:%d/%m/%Y} đến {end:%d/%m/%Y}",
            "total_quantity_sold": sum(row["quantity_sold"] for row in items),
            "total_revenue_vnd": sum(row["revenue_vnd"] for row in items),
            "all_items": items,
            "top_5_best_sellers": items[:5],
            "best_seller": items[0],
            "least_seller": items[-1],
            "source_refs": [f"mcp:postgresql:store:{self.store_id}:table:sales_daily:{start}:{end}", "table:sales_daily"],
        }


def create_server(reader=None):
    reader = reader or PostgresReader()
    server = MCPServer("BeverageOps PostgreSQL", instructions="Chỉ đọc dữ liệu vận hành của cửa hàng được máy chủ cấu hình.")
    hints = types.ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

    @server.tool(annotations=hints, structured_output=True)
    def get_data_coverage() -> dict[str, object]:
        """Read the configured store's available sales date range. No account information."""
        try:
            return reader.coverage()
        except Exception:
            return {"status": "MCP_DATABASE_ERROR", "message": "Không đọc được PostgreSQL. Kiểm tra kết nối và quyền chỉ đọc."}

    @server.tool(annotations=hints, structured_output=True)
    def get_daily_sales(start_date: str | None = None, end_date: str | None = None) -> dict[str, object]:
        """Read sales aggregates for ISO dates YYYY-MM-DD (max366 days). Store comes from server configuration."""
        try:
            return reader.sales(start_date, end_date)
        except ValueError:
            return {"status": "INVALID_ARGUMENTS", "message": "Khoảng ngày không hợp lệ hoặc thiếu cấu hình PostgreSQL/cửa hàng."}
        except Exception:
            return {"status": "MCP_DATABASE_ERROR", "message": "Không đọc được PostgreSQL. Không coi lỗi là dữ liệu rỗng."}

    return server


if __name__ == "__main__":
    create_server().run(transport="stdio")
