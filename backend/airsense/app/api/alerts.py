from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Request, status
from sqlalchemy import func, select, update

from airsense.app.core.errors import Conflict, NotFound
from airsense.app.core.ratelimit import limiter
from airsense.app.db.models import Alert, AlertRule, IngestionRun
from airsense.app.db.session import SessionLocal
from airsense.app.deps import DB, AdminUser, CurrentUser
from airsense.app.schemas import (
    AlertOut,
    AlertRuleIn,
    AlertRuleOut,
    AlertRuleUpdate,
    EvaluateOut,
    IngestionRunOut,
    Message,
    Page,
)
from airsense.app.services import alerting, ingestion
from airsense.app.services.data import get_station

router = APIRouter(prefix="/alerts", tags=["Alerts"])
ingest_router = APIRouter(prefix="/ingestion", tags=["Data ingestion (admin)"])
MAX_RULES = 20


def _own_rule(db, user, rule_id: int) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if rule is None or rule.user_id != user.id:   # don't leak other users' rule ids
        raise NotFound("Alert rule not found.")
    return rule


@router.get("", response_model=Page[AlertOut])
def list_alerts(user: CurrentUser, db: DB, unread_only: bool = False, page: Annotated[int, Query(ge=1)] = 1,
                page_size: Annotated[int, Query(ge=1, le=100)] = 20):
    q = select(Alert).where(Alert.user_id == user.id)
    if unread_only:
        q = q.where(Alert.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = db.execute(q.order_by(Alert.created_at.desc(), Alert.id.desc()).offset((page - 1) * page_size)
                       .limit(page_size)).scalars().all()
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


@router.get("/unread-count")
def unread_count(user: CurrentUser, db: DB):
    return {"unread": db.scalar(select(func.count(Alert.id)).where(Alert.user_id == user.id, Alert.is_read.is_(False)))}


@router.post("/{alert_id}/read", response_model=AlertOut)
def mark_read(alert_id: int, user: CurrentUser, db: DB):
    a = db.get(Alert, alert_id)
    if a is None or a.user_id != user.id:
        raise NotFound("Alert not found.")
    a.is_read = True
    db.commit()
    return a


@router.post("/read-all", response_model=Message)
def read_all(user: CurrentUser, db: DB):
    n = db.execute(update(Alert).where(Alert.user_id == user.id, Alert.is_read.is_(False)).values(is_read=True)).rowcount
    db.commit()
    return Message(message=f"{n} alerts marked as read.")


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(alert_id: int, user: CurrentUser, db: DB):
    a = db.get(Alert, alert_id)
    if a is None or a.user_id != user.id:
        raise NotFound("Alert not found.")
    db.delete(a)
    db.commit()


@router.get("/rules", response_model=list[AlertRuleOut])
def list_rules(user: CurrentUser, db: DB):
    return db.execute(select(AlertRule).where(AlertRule.user_id == user.id).order_by(AlertRule.created_at)).scalars().all()


@router.post("/rules", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(body: AlertRuleIn, user: CurrentUser, db: DB):
    get_station(db, body.station_id)
    if db.scalar(select(func.count(AlertRule.id)).where(AlertRule.user_id == user.id)) >= MAX_RULES:
        raise Conflict(f"You can have at most {MAX_RULES} alert rules.")
    rule = AlertRule(user_id=user.id, **body.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=AlertRuleOut)
def update_rule(rule_id: int, body: AlertRuleUpdate, user: CurrentUser, db: DB):
    rule = _own_rule(db, user, rule_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    db.commit()
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, user: CurrentUser, db: DB):
    db.delete(_own_rule(db, user, rule_id))
    db.commit()


@router.post("/evaluate", response_model=EvaluateOut)
@limiter.limit("10/minute")
def evaluate(request: Request, user: CurrentUser, db: DB):
    """Evaluate the caller's active rules against the latest forecasts and observations now."""
    n, created = alerting.evaluate_rules(db, user)
    return {"rules_evaluated": n, "alerts_created": len(created), "alerts": created}


# ------------------------------------------------------------------ ingestion (admin)
def _run_sync(days: int, user_id: int):
    db = SessionLocal()
    try:
        ingestion.incremental_sync(db, days, user_id)
    finally:
        db.close()


@ingest_router.post("/runs", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def trigger(background: BackgroundTasks, admin: AdminUser, days: Annotated[int, Query(ge=1, le=30)] = 7):
    background.add_task(_run_sync, days, admin.id)
    return Message(message=f"Incremental sync of the last {days} days started.")


@ingest_router.get("/runs", response_model=list[IngestionRunOut])
def runs(_: AdminUser, db: DB, limit: Annotated[int, Query(ge=1, le=100)] = 20):
    return db.execute(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(limit)).scalars().all()
