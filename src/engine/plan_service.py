"""Persist operational drafts and approvals across browser and server sessions."""
import time
from copy import deepcopy

from src.database import Base, SessionLocal, engine
from src.models import OperationPlan

Base.metadata.create_all(bind=engine)


_CACHE: dict = {"at": 0.0, "plans": None}
_TTL = 15.0  # seconds; every write in this process clears it at once


def _invalidate():
    _CACHE["plans"] = None


def save_plan(plan):
    with SessionLocal() as db:
        row = db.get(OperationPlan, plan["plan_id"])
        if row is None:
            row = OperationPlan(plan_id=plan["plan_id"])
            db.add(row)
        row.payload = deepcopy(plan)
        db.commit()
    _invalidate()


def get_plan(plan_id):
    with SessionLocal() as db:
        row = db.get(OperationPlan, plan_id)
        return deepcopy(row.payload) if row else None


def list_plans(plan_type=None):
    """All plans, newest first. Read from the database at most every few seconds (pages call this on every run)."""
    if _CACHE["plans"] is None or time.monotonic() - _CACHE["at"] > _TTL:
        with SessionLocal() as db:
            _CACHE["plans"] = [row.payload for row in db.query(OperationPlan).order_by(OperationPlan.created_at.desc()).all()]
        _CACHE["at"] = time.monotonic()
    return [deepcopy(p) for p in _CACHE["plans"] if not plan_type or p["plan_type"] == plan_type]
