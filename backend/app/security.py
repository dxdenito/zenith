from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(subject: str, kind: str, expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "type": kind, "iat": now, "exp": now + expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def read_token(token: str, kind: str) -> str:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != kind:
        raise jwt.InvalidTokenError("wrong token type")
    return payload["sub"]
