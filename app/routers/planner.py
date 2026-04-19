import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, default_connection
from ..models import Insight, OdooConnection, User
from ..schemas import ApplyPlanRequest, BreakdownRequest, PlanRequest
from ..services import claude
from ..services.context_builder import build_project_pack
from ..services.odoo import (
    create_task,
    creds_from,
    get_task,
    stage_id_by_name,
)

router = APIRouter(prefix="/planner", tags=["planner"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{project_id}", response_class=HTMLResponse)
def planner_page(
    project_id: int,
    request: Request,
    user: User = Depends(current_user),
    conn: OdooConnection = Depends(default_connection),
):
    c = creds_from(conn)
    pack = build_project_pack(c, project_id)
    return templates.TemplateResponse(
        request, "planner.html", {"user": user, "project_id": project_id, "pack": pack}
    )


@router.post("/plan")
def generate_plan(
    req: PlanRequest,
    user: User = Depends(current_user),
    conn: OdooConnection = Depends(default_connection),
    db: Session = Depends(get_db),
):
    c = creds_from(conn)
    pack = build_project_pack(c, req.project_id)
    user_msg = (
        f"Brief:\n{req.brief}\n\n"
        f"Target date: {req.target_date or 'not specified'}\n\n"
        "Return STRICT JSON only, per the schema."
    )
    plan = claude.call_json(
        feature="plan",
        user_message=user_msg,
        project_context=pack,
        user_id=user.id,
    )

    # Save as a local Insight for audit.
    body = "```json\n" + json.dumps(plan, indent=2)[:4000] + "\n```"
    h = hashlib.sha256(body.encode()).hexdigest()[:16]
    try:
        db.add(
            Insight(
                user_id=user.id,
                connection_id=conn.id,
                project_id=req.project_id,
                kind="plan",
                severity="info",
                title=f"Plan drafted: {req.brief[:80]}",
                body_md=body,
                content_hash=h,
            )
        )
        db.commit()
    except Exception:
        db.rollback()

    return plan


@router.post("/apply")
def apply_plan(
    req: ApplyPlanRequest,
    user: User = Depends(current_user),
    conn: OdooConnection = Depends(default_connection),
):
    c = creds_from(conn)
    name_to_id: dict[str, int] = {}
    created: list[dict] = []

    # First pass — create without dependencies.
    for t in req.tasks:
        stage_id = stage_id_by_name(c, req.project_id, t.stage) if t.stage else None
        new_id = create_task(
            c,
            project_id=req.project_id,
            name=t.name,
            description=t.description,
            stage_id=stage_id,
            planned_hours=t.estimated_hours or None,
        )
        name_to_id[t.name] = new_id
        created.append({"id": new_id, "name": t.name})

    # Second pass — wire dependencies via depend_on_ids if Odoo has it enabled.
    # We silently skip if the Odoo instance doesn't support dependencies.
    for t in req.tasks:
        deps = [name_to_id[d] for d in t.depends_on if d in name_to_id]
        if not deps:
            continue
        try:
            from ..services.odoo import execute_kw
            execute_kw(
                c,
                "project.task",
                "write",
                [[name_to_id[t.name]], {"depend_on_ids": [(6, 0, deps)]}],
            )
        except Exception:
            # Dependencies module not enabled — not fatal.
            pass

    return {"created": created, "count": len(created)}


@router.post("/breakdown")
def breakdown(
    req: BreakdownRequest,
    user: User = Depends(current_user),
    conn: OdooConnection = Depends(default_connection),
):
    c = creds_from(conn)
    task = get_task(c, req.task_id)
    if not task:
        raise HTTPException(404, f"Task {req.task_id} not found")

    project_id = task["project_id"][0] if task.get("project_id") else None
    pack = build_project_pack(c, project_id) if project_id else {}

    user_msg = (
        f"Parent task: {task['name']}\n"
        f"Description: {task.get('description') or '(empty)'}\n"
        f"Extra context: {req.extra_context or '(none)'}\n"
        "Return STRICT JSON only."
    )
    out = claude.call_json(
        feature="breakdown",
        user_message=user_msg,
        project_context=pack,
        user_id=user.id,
    )

    # Create subtasks with parent_id pointed at the original task.
    created: list[dict] = []
    for sub in out.get("subtasks", []):
        stage_id = (
            stage_id_by_name(c, project_id, sub.get("stage", "")) if project_id else None
        )
        new_id = create_task(
            c,
            project_id=project_id,
            name=sub["name"],
            description=sub.get("description", ""),
            stage_id=stage_id,
            parent_id=req.task_id,
            planned_hours=sub.get("estimated_hours") or None,
        )
        created.append({"id": new_id, "name": sub["name"]})
    return {"parent": req.task_id, "created": created}
