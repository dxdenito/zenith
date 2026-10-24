import uuid

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cookies import ACCESS_COOKIE
from app.database import get_db
from app.models import User
from app.security import read_token

bearer = HTTPBearer(auto_error=False)


async def current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status_code=401, detail="Please sign in again.")
    token = request.cookies.get(ACCESS_COOKIE) or (creds.credentials if creds else None)
    if not token:
        raise unauthorized
    try:
        user_id = uuid.UUID(read_token(token, "access"))
    except (jwt.PyJWTError, ValueError):
        raise unauthorized
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise unauthorized
    return user