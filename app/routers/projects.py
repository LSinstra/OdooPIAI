from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, default_connection
from ..models import Insight, OdooConnection, User
from ..services.odoo import creds_from, get_project, list_tasks

router = APIRouter(tags=["projects"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(
    project_id: int,
    request: Request,
    user: User = Depends(current_user),
    conn: OdooConnection = Depends(default_connection),
    db: Session = Depends(get_db),
):
    c = creds_from(conn)
    project = get_project(c, project_id)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found in Odoo.")
    tasks = list_tasks(c, project_id)
    insights = (
        db.query(Insight)
        .filter_by(user_id=user.id, project_id=project_id, dismissed=False)
        .order_by(desc(Insight.created_at))
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "project_detail.html",
        {"user": user, "project": project, "tasks": tasks, "insights": insights},
    )
