import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import current_user
from app.deriv_oauth import (
    DerivAuthError,
    DerivError,
    authorize_url,
    exchange_code,
    fetch_accounts,
    new_pkce,
    parse_accounts,
)
from app.models import ActiveAccount, DerivAccount, DerivConnection, User
from app.crypto import decrypt, encrypt

router = APIRouter(prefix="/accounts", tags=["accounts"])

OAUTH_COOKIE = "zenith_deriv_oauth"
OAUTH_PATH = "/accounts/deriv"


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    deriv_account_id: str
    account_type: str
    currency: str | None = None


class AccountsOut(BaseModel):
    active_id: uuid.UUID | None
    accounts: list[AccountOut]


class SwitchIn(BaseModel):
    account_id: uuid.UUID


def back(status: str) -> RedirectResponse:
    res = RedirectResponse(f"{settings.frontend_url}/settings?deriv={status}", status_code=302)
    res.delete_cookie(OAUTH_COOKIE, path=OAUTH_PATH, domain=settings.cookie_domain)
    return res


async def account_list(db: AsyncSession, user: User) -> AccountsOut:
    rows = (
        await db.scalars(
            select(DerivAccount)
            .join(DerivConnection, DerivAccount.connection_id == DerivConnection.id)
            .where(
                DerivAccount.tenant_id == user.tenant_id,
                DerivConnection.tenant_id == user.tenant_id,
                DerivConnection.user_id == user.id,
            )
            .order_by(DerivAccount.account_type.asc(), DerivAccount.created_at.asc())
        )
    ).all()
    active = await db.get(ActiveAccount, user.id)
    active_id = active.account_id if active and any(r.id == active.account_id for r in rows) else None
    return AccountsOut(active_id=active_id, accounts=[AccountOut.model_validate(r) for r in rows])


async def set_active(db: AsyncSession, user: User, account_id: uuid.UUID) -> None:
    current = await db.get(ActiveAccount, user.id)
    if current:
        current.account_id = account_id
    else:
        db.add(ActiveAccount(user_id=user.id, tenant_id=user.tenant_id, account_id=account_id))


async def ensure_active(db: AsyncSession, user: User) -> None:
    listing = await account_list(db, user)
    if listing.active_id is None and listing.accounts:
        await set_active(db, user, listing.accounts[0].id)


async def save_connection(db: AsyncSession, user: User, token: dict) -> DerivConnection:
    connection = await db.scalar(
        select(DerivConnection)
        .where(DerivConnection.tenant_id == user.tenant_id, DerivConnection.user_id == user.id)
        .order_by(DerivConnection.created_at.desc())
        .limit(1)
    )
    if connection is None:
        connection = DerivConnection(tenant_id=user.tenant_id, user_id=user.id, access_token_enc="")
        db.add(connection)
    refresh = token.get("refresh_token")
    expires_in = token.get("expires_in")
    connection.access_token_enc = encrypt(token["access_token"])
    connection.refresh_token_enc = encrypt(refresh) if refresh else None
    connection.scopes = str(token.get("scope", settings.deriv_scopes))
    connection.expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)) if expires_in else None
    )
    connection.status = "active"
    return connection


async def sync_accounts(
    db: AsyncSession, user: User, connection: DerivConnection, rows: list[dict]
) -> None:
    existing = {
        a.deriv_account_id: a
        for a in (
            await db.scalars(
                select(DerivAccount).where(
                    DerivAccount.connection_id == connection.id,
                    DerivAccount.tenant_id == user.tenant_id,
                )
            )
        ).all()
    }
    for row in rows:
        found = existing.get(row["account_id"])
        if found:
            found.account_type = row["account_type"]
            found.currency = row["currency"]
        else:
            db.add(
                DerivAccount(
                    tenant_id=user.tenant_id,
                    connection_id=connection.id,
                    deriv_account_id=row["account_id"],
                    account_type=row["account_type"],
                    currency=row["currency"],
                )
            )
    await db.flush()


@router.get("", response_model=AccountsOut)
async def list_accounts(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await account_list(db, user)


@router.post("/active", response_model=AccountsOut)
async def switch_account(
    payload: SwitchIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    listing = await account_list(db, user)
    if not any(a.id == payload.account_id for a in listing.accounts):
        raise HTTPException(status_code=404, detail="Account not found.")
    await set_active(db, user, payload.account_id)
    await db.commit()
    return await account_list(db, user)


@router.post("/deriv/connect")
async def connect(response: Response, user: User = Depends(current_user)):
    verifier, challenge = new_pkce()
    state = secrets.token_urlsafe(24)
    packed = jwt.encode(
        {
            "type": "deriv_oauth",
            "uid": str(user.id),
            "state": state,
            "verifier": verifier,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    response.set_cookie(
        key=OAUTH_COOKIE,
        value=packed,
        max_age=600,
        path=OAUTH_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
    )
    return {"authorize_url": authorize_url(state, challenge)}


@router.get("/deriv/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    packed = request.cookies.get(OAUTH_COOKIE)
    if error or not code or not state or not packed:
        return back("denied")
    try:
        data = jwt.decode(packed, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return back("expired")
    if data.get("type") != "deriv_oauth" or not secrets.compare_digest(data.get("state", ""), state):
        return back("invalid")
    user = await db.scalar(select(User).where(User.id == uuid.UUID(data["uid"])))
    if user is None or not user.is_active:
        return back("invalid")
    try:
        token = await exchange_code(code, data["verifier"])
        accounts = await fetch_accounts(token["access_token"])
    except (DerivError, KeyError, httpx.HTTPError) as exc:
        print(f"[deriv] link failed: {exc!r}")
        return back("failed")
    print(f"[deriv] accounts response: {accounts}")
    connection = await save_connection(db, user, token)
    await db.flush()
    await sync_accounts(db, user, connection, parse_accounts(accounts))
    await ensure_active(db, user)
    await db.commit()
    return back("linked")



class AccountDetail(BaseModel):
    id: uuid.UUID
    deriv_account_id: str
    account_type: str
    currency: str | None = None
    balance: str | None = None


class OverviewOut(BaseModel):
    status: str
    active_id: uuid.UUID | None
    accounts: list[AccountDetail]


@router.get("/overview", response_model=OverviewOut)
async def overview(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    listing = await account_list(db, user)
    details = [
        AccountDetail(
            id=a.id,
            deriv_account_id=a.deriv_account_id,
            account_type=a.account_type,
            currency=a.currency,
        )
        for a in listing.accounts
    ]
    connection = await db.scalar(
        select(DerivConnection)
        .where(DerivConnection.tenant_id == user.tenant_id, DerivConnection.user_id == user.id)
        .order_by(DerivConnection.created_at.desc())
        .limit(1)
    )
    if connection is None or not details:
        return OverviewOut(status="none", active_id=listing.active_id, accounts=details)

    status = "active"
    expired = connection.status != "active" or (
        connection.expires_at is not None and connection.expires_at <= datetime.now(timezone.utc)
    )
    if not expired:
        try:
            payload = await fetch_accounts(decrypt(connection.access_token_enc))
        except DerivAuthError:
            expired = True
        except (DerivError, httpx.HTTPError, ValueError):
            status = "unavailable"
        else:
            raw = payload.get("data", []) if isinstance(payload, dict) else payload
            items = raw if isinstance(raw, list) else [raw]
            balances = {
                str(i.get("account_id")): i.get("balance") for i in items if isinstance(i, dict)
            }
            for detail in details:
                value = balances.get(detail.deriv_account_id)
                detail.balance = str(value) if value is not None else None
    if expired:
        connection.status = "expired"
        await db.commit()
        status = "expired"
    return OverviewOut(status=status, active_id=listing.active_id, accounts=details)