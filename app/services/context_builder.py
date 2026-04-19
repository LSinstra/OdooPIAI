"""Builds the project-context pack we send to Claude.

Goals:
 - deterministic output (stable JSON order -> prompt cache hits)
 - compact (drop empty fields, trim long descriptions)
 - PII-safe (emails/phones stripped when REDACT_PII=true)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..config import get_settings
from .crypto import redact_pii
from .odoo import OdooCreds, get_project, list_stages, list_tasks

_settings = get_settings()


def _clean(text: str | None, limit: int = 600) -> str:
    if not text:
        return ""
    t = text.strip()
    if _settings.REDACT_PII:
        t = redact_pii(t)
    return t[:limit]


def _days_overdue(deadline: str | None) -> int | None:
    if not deadline:
        return None
    try:
        d = datetime.strptime(deadline, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (date.today() - d).days


def build_project_pack(c: OdooCreds, project_id: int) -> dict[str, Any]:
    project = get_project(c, project_id)
    if not project:
        return {"project_id": project_id, "error": "not_found"}

    stages = list_stages(c, project_id)
    tasks = list_tasks(c, project_id)

    compact_tasks: list[dict[str, Any]] = []
    for t in tasks:
        stage_name = t["stage_id"][1] if t.get("stage_id") else None
        parent_name = t["parent_id"][1] if t.get("parent_id") else None
        overdue_days = _days_overdue(t.get("date_deadline") or None)
        compact_tasks.append(
            {
                "id": t["id"],
                "name": t["name"],
                "description": _clean(t.get("description")),
                "stage": stage_name,
                "priority": t.get("priority"),
                "state": t.get("state"),
                "deadline": t.get("date_deadline") or None,
                "overdue_days": overdue_days,
                "allocated_hours": t.get("allocated_hours") or 0,
                "assignees": [u for u in (t.get("user_ids") or [])],
                "parent": parent_name,
                "last_stage_update": t.get("date_last_stage_update") or None,
            }
        )

    return {
        "project": {
            "id": project["id"],
            "name": project["name"],
            "manager": (project.get("user_id") or [None, None])[1],
            "customer": (project.get("partner_id") or [None, None])[1],
            "start": project.get("date_start") or None,
            "end": project.get("date") or None,
            "description": _clean(project.get("description")),
        },
        "stages": [s["name"] for s in stages],
        "task_count": len(compact_tasks),
        "tasks": compact_tasks,
    }
