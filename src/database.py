"""Database sessions: explicit environment/.env URL, otherwise local SQLite.

A configured PostgreSQL failure is surfaced, never replaced by another datastore.
"""
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import make_url
from src.runtime_settings import setting

ROOT = Path(__file__).resolve().parents[1]

# Process environment takes precedence over .env, including an explicit blank.
db_url = setting("DATABASE_URL")
if not db_url:
    # Local SQLite database file for zero-config local development
    sqlite_path = ROOT / "data" / "beverageops.db"
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{sqlite_path.as_posix()}"
else:
    DATABASE_URL = db_url

database_url = make_url(DATABASE_URL.replace('postgres://', 'postgresql://', 1))
if database_url.drivername == 'postgresql':
    database_url = database_url.set(drivername='postgresql+psycopg2')

engine = create_engine(
    database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

if engine.dialect.name == 'sqlite':
    @event.listens_for(engine, 'connect')
    def configure_sqlite(connection, _record):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=5000')
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
