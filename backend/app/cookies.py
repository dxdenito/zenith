from fastapi import Response

from app.config import settings

ACCESS_COOKIE = "zenith_access"
REFRESH_COOKIE = "zenith_refresh"


def _set(response: Response, name: str, value: str, max_age: int, path: str) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        path=path,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
    )


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    _set(response, ACCESS_COOKIE, access, settings.access_token_minutes * 60, "/")
    _set(response, REFRESH_COOKIE, refresh, settings.refresh_token_days * 86400, "/auth")


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=settings.cookie_domain)
    response.delete_cookie(REFRESH_COOKIE, path="/auth", domain=settings.cookie_domain)