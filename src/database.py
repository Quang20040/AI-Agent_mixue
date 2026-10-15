"""Database configuration and session management.
Supports PostgreSQL if available or SQLite local fallback.
"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).resolve().parents[1]

# Check database URL from environment or fallback to local SQLite
db_url = os.getenv("DATABASE_URL")
if not db_url or "postgresql" in db_url and not os.getenv("POSTGRES_ACTIVE"):
    # Local SQLite database file for zero-config local development
    sqlite_path = ROOT / "data" / "beverageops.db"
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{sqlite_path.as_posix()}"
else:
    DATABASE_URL = db_url

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
