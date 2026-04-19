import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Insight, OdooConnection
from ..services import claude
from ..services.context_builder import build_project_pack
from ..services.odoo import creds_from, list_projects

logger = logging.getLogger(__name__)


def run_risk_scan() -> None:
    with SessionLocal() as db:
        conns = db.execute(select(OdooConnection)).scalars().all()
        for conn in conns:
            try:
                _scan_connection(db, conn)
            except Exception:
                logger.exception("risk scan failed for connection %s", conn.id)


def _scan_connection(db: Session, conn: OdooConnection) -> None:
    c = creds_from(conn)
    for p in list_projects(c, limit=15):
        pack = build_project_pack(c, p["id"])
        if not pack.get("tasks"):
            continue

        out = claude.call_json(
            feature="risk",
            user_message="Scan this project's tasks. Return STRICT JSON only.",
            project_context=pack,
            user_id=conn.user_id,
            max_tokens=1500,
        )

        for r in out.get("risks", []):
            title = r.get("title", "Risk").strip()[:255]
            body = r.get("body_md", "").strip()
            sev = r.get("severity", "info")
            if sev not in {"info", "warn", "high"}:
                sev = "info"
            h = hashlib.sha256((title + body).encode()).hexdigest()[:16]
            try:
                db.add(
                    Insight(
                        user_id=conn.user_id,
                        connection_id=conn.id,
                        project_id=p["id"],
                        kind="risk",
                        severity=sev,
                        title=title,
                        body_md=body,
                        content_hash=h,
                    )
                )
                db.commit()
            except Exception:
                # Unique (user, project, hash) constraint — already flagged.
                db.rollback()
