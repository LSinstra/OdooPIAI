from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from ..config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALG = "HS256"
_TOKEN_TTL = timedelta(days=30)


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd.verify(password, hashed)


def make_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + _TOKEN_TTL}
    return jwt.encode(payload, get_settings().JWT_SECRET, algorithm=_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().JWT_SECRET, algorithms=[_ALG])
