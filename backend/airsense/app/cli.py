"""Operational CLI.

    python -m airsense.app.cli migrate          # alembic upgrade head
    python -m airsense.app.cli seed             # load processed pipeline output into the DB
    python -m airsense.app.cli sync --days 7    # incremental ingestion from OpenAQ + Open-Meteo
    python -m airsense.app.cli create-user --email a@b.c --name "Admin" --admin   (password from AIRSENSE_NEW_USER_PASSWORD or prompt)
"""
from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import select


def migrate() -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.upgrade(cfg, "head")


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="airsense")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    sub.add_parser("seed")
    sp = sub.add_parser("sync")
    sp.add_argument("--days", type=int, default=7)
    cu = sub.add_parser("create-user")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--admin", action="store_true")
    a = p.parse_args(argv)

    if a.cmd == "migrate":
        migrate()
        return 0

    from airsense.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        if a.cmd == "seed":
            from airsense.app.services import forecasting, ingestion

            run = ingestion.seed_from_pipeline(db)
            mv = forecasting.sync_model_registry(db)
            print(f"seed {run.status}: {run.rows_upserted} rows; active model: {mv.version if mv else None}")
        elif a.cmd == "sync":
            from airsense.app.services import ingestion

            run = ingestion.incremental_sync(db, a.days)
            print(f"sync {run.status}: {run.rows_upserted} rows")
            return 0 if run.status == "success" else 1
        elif a.cmd == "create-user":
            from airsense.app.core.security import hash_password, validate_password_strength
            from airsense.app.db.models import User, UserPreference

            pw = os.environ.get("AIRSENSE_NEW_USER_PASSWORD") or getpass.getpass("Password: ")
            validate_password_strength(pw)
            u = db.scalar(select(User).where(User.email == a.email.lower()))
            if u is None:
                u = User(email=a.email.lower(), full_name=a.name, hashed_password=hash_password(pw))
                u.preferences = UserPreference()
                db.add(u)
            else:
                u.hashed_password = hash_password(pw)
            u.role = "admin" if a.admin else "user"
            db.commit()
            print(f"user {u.email} ({u.role}) ready")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
