from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import OdooConnection, User
from ..services.crypto import encrypt
from ..services.odoo import OdooCreds, test_connection

router = APIRouter(tags=["settings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    conns = db.query(OdooConnection).filter_by(user_id=user.id).order_by(OdooConnection.id).all()
    return templates.TemplateResponse(
        request, "settings.html", {"user": user, "connections": conns, "status": None}
    )


@router.post("/settings/odoo")
def save_connection(
    request: Request,
    label: str = Form(...),
    url: str = Form(...),
    db_name: str = Form(...),
    username: str = Form(...),
    api_key: str = Form(...),
    is_default: bool = Form(False),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    probe = OdooCreds(url=url.rstrip("/"), db=db_name, username=username, api_key=api_key)
    try:
        result = test_connection(probe)
        if not result["ok"]:
            raise RuntimeError("authentication failed")
    except Exception as e:
        conns = db.query(OdooConnection).filter_by(user_id=user.id).all()
        return templates.TemplateResponse(
            request,
            "settings.html",
            {
                "user": user,
                "connections": conns,
                "status": {"ok": False, "msg": f"Odoo test failed: {e}"},
            },
            status_code=400,
        )

    if is_default:
        db.query(OdooConnection).filter_by(user_id=user.id).update({"is_default": False})

    conn = OdooConnection(
        user_id=user.id,
        label=label,
        url=url.rstrip("/"),
        db_name=db_name,
        username=username,
        api_key_ct=encrypt(api_key),
        is_default=is_default,
    )
    db.add(conn)
    db.commit()
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/odoo/{conn_id}/delete")
def delete_connection(
    conn_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    conn = db.get(OdooConnection, conn_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(404)
    db.delete(conn)
    db.commit()
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/odoo/{conn_id}/default")
def set_default(
    conn_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    conn = db.get(OdooConnection, conn_id)
    if not conn or conn.user_id != user.id:
        raise HTTPException(404)
    db.query(OdooConnection).filter_by(user_id=user.id).update({"is_default": False})
    conn.is_default = True
    db.commit()
    return RedirectResponse("/settings", status_code=303)
