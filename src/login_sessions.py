"""Keep a signed-in user signed in across page reloads.

Streamlit forgets everything on reload (a reload is a new session). After a successful login the app
puts a random token in the page address (?s=…); a reload sends it back and the user is restored.
Only a SHA-256 of the token is stored, tokens expire after 12 hours without use, and signing out or a
deactivated account ends them.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from src.database import SessionLocal

LIFETIME = timedelta(hours=12)
QUERY_KEY = 's'


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ensure(db) -> None:
    db.execute(text('CREATE TABLE IF NOT EXISTS login_sessions ('
                    'token_hash VARCHAR(64) PRIMARY KEY, username VARCHAR(50) NOT NULL, expires_at TIMESTAMP NOT NULL)'))


def create(username: str) -> str:
    token = secrets.token_urlsafe(24)
    with SessionLocal() as db:
        _ensure(db)
        db.execute(text('DELETE FROM login_sessions WHERE expires_at < :now'), {'now': _now()})
        db.execute(text('INSERT INTO login_sessions (token_hash, username, expires_at) VALUES (:h, :u, :e)'),
                   {'h': _digest(token), 'u': username, 'e': _now() + LIFETIME})
        db.commit()
    return token


def restore(token: str | None) -> dict[str, Any] | None:
    """The user dict verify_user() would return, or None for an unknown/expired token or inactive account."""
    if not token or len(token) > 64:
        return None
    from src.auth import _get_role_metadata, normalize_role
    from src.models import User
    with SessionLocal() as db:
        _ensure(db)
        row = db.execute(text('SELECT username, expires_at FROM login_sessions WHERE token_hash = :h'),
                         {'h': _digest(token)}).fetchone()
        if not row:
            return None
        expires = row[1] if isinstance(row[1], datetime) else datetime.fromisoformat(str(row[1]))
        if expires < _now():
            return None
        user = db.get(User, row[0])
        if not user or not user.is_active or normalize_role(user.role) not in {
                'ADMIN', 'MANAGER', 'OWNER', 'STAFF_OFFICIAL', 'STAFF_PROBATION'}:
            return None
        db.execute(text('UPDATE login_sessions SET expires_at = :e WHERE token_hash = :h'),
                   {'e': _now() + LIFETIME, 'h': _digest(token)})
        db.commit()
        meta = _get_role_metadata(user.role, user.username)
        return {'username': user.username, 'name': user.full_name, 'phone': user.phone or '', 'role': user.role,
                'title': meta['title'], 'badge': meta['badge'], 'description': meta['description'],
                'must_change_password': bool(user.must_change_password), 'is_active': bool(user.is_active)}


def revoke(token: str | None) -> None:
    if not token:
        return
    with SessionLocal() as db:
        _ensure(db)
        db.execute(text('DELETE FROM login_sessions WHERE token_hash = :h'), {'h': _digest(token)})
        db.commit()
