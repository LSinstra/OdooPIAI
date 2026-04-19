from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user_optional
from ..models import Insight, OdooConnection, User
from ..services.odoo import creds_from, list_projects

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    user: User | None = Depends(current_user_optional),
    db: Session = Depends(get_db),
):
    if not user:
        return RedirectResponse("/login")

    conn = (
        db.query(OdooConnection)
        .filter_by(user_id=user.id, is_default=True)
        .first()
        or db.query(OdooConnection).filter_by(user_id=user.id).first()
    )
    if not conn:
        return RedirectResponse("/settings")

    projects: list[dict] = []
    odoo_err: str | None = None
    try:
        projects = list_projects(creds_from(conn), limit=25)
    except Exception as e:
        odoo_err = str(e)

    recent = (
        db.query(Insight)
        .filter_by(user_id=user.id, dismissed=False)
        .order_by(desc(Insight.created_at))
        .limit(8)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "connection": conn,
            "projects": projects,
            "insights": recent,
            "odoo_err": odoo_err,
        },
    )
