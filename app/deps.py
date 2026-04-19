from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import OdooConnection, User
from .services.auth import decode_token


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    session: str | None = Cookie(default=None),
) -> User:
    token = session or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


def current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    session: str | None = Cookie(default=None),
) -> User | None:
    try:
        return current_user(request=request, db=db, session=session)
    except HTTPException:
        return None


def default_connection(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> OdooConnection:
    conn = (
        db.query(OdooConnection)
        .filter_by(user_id=user.id, is_default=True)
        .first()
    )
    if not conn:
        conn = db.query(OdooConnection).filter_by(user_id=user.id).first()
    if not conn:
        raise HTTPException(400, "No Odoo connection configured. Add one in Settings.")
    return conn
