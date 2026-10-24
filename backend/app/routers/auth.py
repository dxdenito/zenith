import re
import uuid
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.database import get_db
from app.deps import current_user
from app.models import Tenant, User
from app.schemas import LoginIn, RegisterIn, UserOut
from app.security import create_token, hash_password, read_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "workspace"
    return f"{base[:40]}-{uuid.uuid4().hex[:6]}"


def start_session(response: Response, user: User) -> UserOut:
    subject = str(user.id)
    access = create_token(subject, "access", timedelta(minutes=settings.access_token_minutes))
    refresh = create_token(subject, "refresh", timedelta(days=settings.refresh_token_days))
    set_auth_cookies(response, access, refresh)
    return UserOut.model_validate(user)


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: RegisterIn, response: Response, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="That email already has an account. Try signing in.")
    full_name = payload.full_name.strip()
    workspace = (payload.workspace_name or "").strip() or f"{full_name}'s workspace"
    tenant = Tenant(name=workspace, slug=slugify(workspace))
    user = User(
        tenant=tenant,
        email=email,
        full_name=full_name,
        password_hash=hash_password(payload.password),
        role="owner",
    )
    db.add(user)
    await db.commit()
    return start_session(response, user)


@router.post("/login", response_model=UserOut)
async def login(payload: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password.")
    return start_session(response, user)


@router.post("/refresh", response_model=UserOut)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    expired = HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise expired
    try:
        user_id = uuid.UUID(read_token(token, "refresh"))
    except (jwt.PyJWTError, ValueError):
        raise expired
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise expired
    return start_session(response, user)


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return UserOut.model_validate(user)