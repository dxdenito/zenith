import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx

from app.config import settings

AUTH_URL = "https://auth.deriv.com/oauth2/auth"
TOKEN_URL = "https://auth.deriv.com/oauth2/token"
ACCOUNTS_URL = "https://api.derivws.com/trading/v1/options/accounts"


class DerivError(Exception):
    pass

class DerivAuthError(DerivError):
    pass


def new_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def authorize_url(state: str, challenge: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.deriv_app_id,
            "redirect_uri": settings.deriv_redirect_uri,
            "scope": settings.deriv_scopes,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTH_URL}?{query}"


async def exchange_code(code: str, verifier: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.deriv_app_id,
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": settings.deriv_redirect_uri,
            },
        )
    if res.status_code != 200:
        raise DerivError(f"Token exchange failed ({res.status_code}): {res.text[:300]}")
    return res.json()


async def fetch_accounts(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.get(ACCOUNTS_URL, headers={"Authorization": f"Bearer {access_token}"})
    if res.status_code in (401, 403):
        raise DerivAuthError(f"Deriv rejected the token ({res.status_code})")
    if res.status_code != 200:
        raise DerivError(f"Accounts request failed ({res.status_code}): {res.text[:300]}")
    return res.json()


def parse_accounts(payload) -> list[dict]:
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        data = [data]
    rows = []
    for item in data or []:
        if not isinstance(item, dict):
            continue
        account_id = item.get("account_id")
        kind = item.get("account_type")
        if account_id and kind in ("demo", "real"):
            rows.append(
                {"account_id": str(account_id), "account_type": kind, "currency": item.get("currency")}
            )
    return rows