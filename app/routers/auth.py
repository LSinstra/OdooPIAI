from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..services.auth import hash_password, make_token, verify_password

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter_by(email=email.lower().strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "login.html", {"error": "Invalid email or password."}, status_code=400
        )
    token = make_token(user.id)
    resp = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30
    )
    return resp


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None})


@router.post("/register")
def register(
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(""),
    db: Session = Depends(get_db),
):
    email = email.lower().strip()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(400, "Email already registered.")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    user = User(email=email, password_hash=hash_password(password), name=name or None)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = make_token(user.id)
    resp = RedirectResponse("/settings", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30
    )
    return resp


@router.post("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("session")
    return resp
