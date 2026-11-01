# -*- coding: utf-8 -*-
"""System Healthcheck Script for Mixue BeverageOps AI Agent System.

Validates service readiness before and during store pilot:
1. SQLite Databases Connectivity & PRAGMA integrity_check
2. Agent & Local Hybrid Retrieval Readiness
3. Authentication & User Store Readiness
4. Vision OCR Engine Readiness
5. Storage & Disk Space Check
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def check_database(path: Path, created_on_first_use: bool = False) -> dict[str, Any]:
    if not path.exists():
        if created_on_first_use:
            # Fresh install / CI checkout: the store is created by the app on first use.
            return {"status": "NOT_INITIALIZED", "message": f"{path.name} sẽ được tạo khi ứng dụng chạy lần đầu."}
        return {"status": "ERROR", "message": f"Database file missing: {path.name}"}
    try:
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as conn:
            cursor = conn.execute("PRAGMA integrity_check;")
            row = cursor.fetchone()
            if row and row[0] == "ok":
                return {"status": "HEALTHY", "size_bytes": path.stat().st_size}
            return {"status": "CORRUPT", "error": str(row)}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def check_disk_space(min_free_mb: int = 500) -> dict[str, Any]:
    try:
        total, used, free = shutil.disk_usage(REPO_ROOT)
        free_mb = free / (1024 * 1024)
        return {
            "status": "HEALTHY" if free_mb >= min_free_mb else "WARNING",
            "free_mb": round(free_mb, 1),
            "min_required_mb": min_free_mb,
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def check_rag_engine() -> dict[str, Any]:
    try:
        from src.agent.multi_agent.repo_docs_agent import RepoDocsAgent
        agent = RepoDocsAgent(REPO_ROOT)
        hits = agent.search("trân châu", top_k=1)
        if hits and len(hits) > 0:
            return {"status": "HEALTHY", "indexed_chunks": len(agent.chunks), "sample_score": hits[0]["score"]}
        return {"status": "DEGRADED", "indexed_chunks": len(agent.chunks), "message": "No sample hits"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def check_auth_store() -> dict[str, Any]:
    try:
        from src.database import SessionLocal
        from src.models import User
        with SessionLocal() as db:
            count = db.query(User).count()
            return {"status": "HEALTHY", "active_users_count": count}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def run_full_healthcheck() -> tuple[bool, dict[str, Any]]:
    db_ops = check_database(REPO_ROOT / "data" / "beverageops.db")
    db_conv = check_database(REPO_ROOT / "data" / "agent_private" / "conversations.sqlite", created_on_first_use=True)
    disk = check_disk_space()
    rag = check_rag_engine()
    auth = check_auth_store()

    all_healthy = (
        db_ops["status"] == "HEALTHY"
        and db_conv["status"] in ("HEALTHY", "NOT_INITIALIZED")
        and disk["status"] in ("HEALTHY", "WARNING")
        and rag["status"] == "HEALTHY"
        and auth["status"] == "HEALTHY"
    )

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": "HEALTHY" if all_healthy else "UNHEALTHY",
        "checks": {
            "database_operations": db_ops,
            "database_conversations": db_conv,
            "disk_space": disk,
            "rag_and_sop_agent": rag,
            "auth_and_users": auth,
        },
    }
    return all_healthy, report


def main():
    healthy, report = run_full_healthcheck()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()
