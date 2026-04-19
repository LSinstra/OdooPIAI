from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import AppSetting, OdooConnection, User
from ..services.crypto import decrypt, encrypt
from ..services.odoo import OdooCreds, normalize_url, test_connection

router = APIRouter(tags=["settings"])
templates = Jinja2Templates(directory="app/templates")


def _app_setting(db: Session) -> AppSetting:
    row = db.get(AppSetting, 1)
    if not row:
        row = AppSetting(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _mask(key: str | None) -> str:
    if not key:
        return ""
    return f"{key[:7]}…{key[-4:]}" if len(key) > 12 else "set"


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    conns = db.query(OdooConnection).filter_by(user_id=user.id).order_by(OdooConnection.id).all()
    app_s = _app_setting(db)
    key_masked = ""
    if app_s.anthropic_api_key_ct:
        try:
            key_masked = _mask(decrypt(app_s.anthropic_api_key_ct))
        except Exception:
            key_masked = "(decryption failed)"

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "user": user,
            "connections": conns,
            "status": None,
            "anthropic_key_masked": key_masked,
            "anthropic_model": app_s.anthropic_model or "",
        },
    )


@router.post("/settings/anthropic")
def save_anthropic(
    anthropic_api_key: str = Form(""),
    anthropic_model: str = Form(""),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = _app_setting(db)
    key = anthropic_api_key.strip()
    if key:
        # Only overwrite when a new key was typed — blank keeps the existing.
        row.anthropic_api_key_ct = encrypt(key)
    row.anthropic_model = anthropic_model.strip() or None
    db.commit()
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/anthropic/clear")
def clear_anthropic(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = _app_setting(db)
    row.anthropic_api_key_ct = None
    db.commit()
    return RedirectResponse("/settings", status_code=303)


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
    probe = OdooCreds(url=normalize_url(url), db=db_name, username=username, api_key=api_key)
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
        url=normalize_url(url),
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
