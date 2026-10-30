"""Read-only, credential-free local setup diagnostics. Does not import app models."""

import importlib.util
import json
from pathlib import Path
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.engine import make_url
from src.runtime_settings import setting


def diagnose():
    import os
    source = 'process_environment' if 'DATABASE_URL' in os.environ else '.env'
    if not setting('DATABASE_URL'):
        source = 'default_local_sqlite'
    report = {"mcp_enabled": setting("POSTGRES_MCP_ENABLED", "false").lower() == "true",
              "application_database_source": source}
    for name in ("DATABASE_URL", "POSTGRES_MCP_DATABASE_URL"):
        raw = setting(name)
        if not raw:
            report[name] = {"configured": False}
            continue
        try:
            url = make_url(raw)
            item = {"configured": True, "driver": url.drivername, "host": url.host, "port": url.port, "database": url.database}
            if url.get_backend_name() == "postgresql":
                port = url.port or 5432
                try:
                    with socket.create_connection((url.host or "localhost", port), timeout=2):
                        item["port_reachable"] = True
                except OSError:
                    item["port_reachable"] = False
                module = "psycopg" if url.drivername.endswith("+psycopg") else "psycopg2"
                item["driver_installed"] = importlib.util.find_spec(module) is not None
            report[name] = item
        except Exception:
            report[name] = {"configured": True, "error": "INVALID_CONFIGURATION"}
    return report


if __name__ == "__main__":
    print(json.dumps(diagnose(), indent=2, ensure_ascii=True))
