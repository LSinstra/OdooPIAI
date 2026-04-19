from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from ..config import get_settings

_ALG = "HS256"
_TOKEN_TTL = timedelta(days=30)
_BCRYPT_MAX = 72  # bcrypt hard limit; we truncate silently (min-length is enforced upstream).


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_BCRYPT_MAX]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:_BCRYPT_MAX], hashed.encode())
    except ValueError:
        return False


def make_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + _TOKEN_TTL}
    return jwt.encode(payload, get_settings().JWT_SECRET, algorithm=_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().JWT_SECRET, algorithms=[_ALG])
