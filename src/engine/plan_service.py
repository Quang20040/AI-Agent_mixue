"""Persist operational drafts and approvals across browser and server sessions."""
from copy import deepcopy

from src.database import Base, SessionLocal, engine
from src.models import OperationPlan

Base.metadata.create_all(bind=engine)


def save_plan(plan):
    with SessionLocal() as db:
        row = db.get(OperationPlan, plan["plan_id"])
        if row is None:
            row = OperationPlan(plan_id=plan["plan_id"])
            db.add(row)
        row.payload = deepcopy(plan)
        db.commit()


def get_plan(plan_id):
    with SessionLocal() as db:
        row = db.get(OperationPlan, plan_id)
        return deepcopy(row.payload) if row else None


def list_plans(plan_type=None):
    with SessionLocal() as db:
        plans = [deepcopy(row.payload) for row in db.query(OperationPlan).order_by(OperationPlan.created_at.desc()).all()]
        return [p for p in plans if not plan_type or p["plan_type"] == plan_type]
