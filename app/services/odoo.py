"""Thin wrapper around Odoo 17 XML-RPC.

We keep the surface small — just the project.project, project.task, res.users,
and mail.message calls we actually need. Everything returns dicts so routers
don't need to know anything about xmlrpc.client.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from xmlrpc.client import ServerProxy

from ..models import OdooConnection
from .crypto import decrypt


@dataclass
class OdooCreds:
    url: str
    db: str
    username: str
    api_key: str


def normalize_url(url: str) -> str:
    """Add https:// if the user omitted the scheme, and strip trailing slashes.

    xmlrpc.client.ServerProxy raises 'unsupported XML-RPC protocol' otherwise.
    """
    u = (url or "").strip().rstrip("/")
    if not u:
        return u
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u


def creds_from(conn: OdooConnection) -> OdooCreds:
    return OdooCreds(
        url=normalize_url(conn.url),
        db=conn.db_name,
        username=conn.username,
        api_key=decrypt(conn.api_key_ct),
    )


@lru_cache(maxsize=64)
def _uid_for(url: str, db: str, username: str, api_key: str) -> int:
    common = ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, username, api_key, {})
    if not uid:
        raise RuntimeError("Odoo authentication failed — check URL/db/username/API key.")
    return uid


def _models(url: str) -> ServerProxy:
    return ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)


def execute_kw(
    c: OdooCreds,
    model: str,
    method: str,
    args: list | None = None,
    kwargs: dict | None = None,
) -> Any:
    uid = _uid_for(c.url, c.db, c.username, c.api_key)
    return _models(c.url).execute_kw(
        c.db, uid, c.api_key, model, method, args or [], kwargs or {}
    )


# ---- High level helpers --------------------------------------------
def test_connection(c: OdooCreds) -> dict:
    """Try to authenticate + read server version. Returns diagnostic dict."""
    common = ServerProxy(f"{c.url}/xmlrpc/2/common", allow_none=True)
    version = common.version()
    uid = common.authenticate(c.db, c.username, c.api_key, {})
    return {"uid": uid, "version": version, "ok": bool(uid)}


def list_projects(c: OdooCreds, limit: int = 50) -> list[dict]:
    return execute_kw(
        c,
        "project.project",
        "search_read",
        [[["active", "=", True]]],
        {
            "fields": ["id", "name", "user_id", "partner_id", "date_start", "date", "description"],
            "limit": limit,
            "order": "id desc",
        },
    )


def get_project(c: OdooCreds, project_id: int) -> dict | None:
    rows = execute_kw(
        c,
        "project.project",
        "read",
        [[project_id]],
        {"fields": ["id", "name", "user_id", "partner_id", "date_start", "date", "description"]},
    )
    return rows[0] if rows else None


def list_tasks(c: OdooCreds, project_id: int, limit: int = 200) -> list[dict]:
    return execute_kw(
        c,
        "project.task",
        "search_read",
        [[["project_id", "=", project_id]]],
        {
            "fields": [
                "id",
                "name",
                "description",
                "stage_id",
                "user_ids",
                "date_deadline",
                "date_last_stage_update",
                "priority",
                "parent_id",
                "depend_on_ids",
                "allocated_hours",
                "state",
            ],
            "limit": limit,
            "order": "date_deadline asc, id desc",
        },
    )


def list_stages(c: OdooCreds, project_id: int) -> list[dict]:
    return execute_kw(
        c,
        "project.task.type",
        "search_read",
        [[["project_ids", "in", [project_id]]]],
        {"fields": ["id", "name", "sequence"], "order": "sequence asc"},
    )


def stage_id_by_name(c: OdooCreds, project_id: int, name: str) -> int | None:
    for s in list_stages(c, project_id):
        if s["name"].lower() == name.lower():
            return s["id"]
    return None


def create_task(
    c: OdooCreds,
    *,
    project_id: int,
    name: str,
    description: str = "",
    stage_id: int | None = None,
    parent_id: int | None = None,
    planned_hours: float | None = None,
    date_deadline: str | None = None,
) -> int:
    vals: dict[str, Any] = {
        "project_id": project_id,
        "name": name,
        "description": description,
    }
    if stage_id:
        vals["stage_id"] = stage_id
    if parent_id:
        vals["parent_id"] = parent_id
    if planned_hours is not None:
        vals["allocated_hours"] = planned_hours
    if date_deadline:
        vals["date_deadline"] = date_deadline
    return execute_kw(c, "project.task", "create", [vals])


def get_task(c: OdooCreds, task_id: int) -> dict | None:
    rows = execute_kw(
        c,
        "project.task",
        "read",
        [[task_id]],
        {"fields": ["id", "name", "description", "project_id", "stage_id", "allocated_hours"]},
    )
    return rows[0] if rows else None


def post_chatter(c: OdooCreds, *, model: str, res_id: int, body_html: str, subject: str | None = None) -> int:
    return execute_kw(
        c,
        model,
        "message_post",
        [[res_id]],
        {
            "body": body_html,
            "subject": subject,
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_note",
        },
    )
