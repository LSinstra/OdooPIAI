import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Insight, OdooConnection
from ..services import claude
from ..services.context_builder import build_project_pack
from ..services.odoo import creds_from, list_projects, post_chatter

logger = logging.getLogger(__name__)


def run_daily_digest() -> None:
    """For every active connection, produce a digest for up to 10 projects."""
    with SessionLocal() as db:
        conns = db.execute(select(OdooConnection)).scalars().all()
        for conn in conns:
            try:
                _run_for_connection(db, conn)
            except Exception:
                logger.exception("digest failed for connection %s", conn.id)


def _run_for_connection(db: Session, conn: OdooConnection) -> None:
    c = creds_from(conn)
    projects = list_projects(c, limit=10)
    for p in projects:
        pack = build_project_pack(c, p["id"])
        if not pack.get("tasks"):
            continue

        text, _ = claude.call(
            feature="digest",
            user_message="Produce today's standup digest for this project.",
            project_context=pack,
            user_id=conn.user_id,
            max_tokens=800,
        )

        h = hashlib.sha256(text.encode()).hexdigest()[:16]
        ins = Insight(
            user_id=conn.user_id,
            connection_id=conn.id,
            project_id=p["id"],
            kind="digest",
            severity="info",
            title=f"Daily digest — {p['name']}",
            body_md=text,
            content_hash=h,
        )
        try:
            db.add(ins)
            db.commit()
        except Exception:
            db.rollback()

        # Also post to Odoo chatter so the team sees it where they already work.
        try:
            html = "<pre>" + text.replace("<", "&lt;") + "</pre>"
            post_chatter(c, model="project.project", res_id=p["id"], subject="Daily digest", body_html=html)
        except Exception:
            logger.exception("chatter post failed for project %s", p["id"])
