"""Google sign-in endpoints: login redirect, OAuth callback, session, logout."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.config.settings import Settings, get_settings
from app.database.session import get_db
from app.services.auth import google as goog
from app.services.auth.tokens import sign, verify
from app.services.auth.users import AuthUserService

router = APIRouter(prefix="/auth", tags=["auth"])

_STATE_COOKIE = "gads_oauth_state"
_STATE_TTL = 600  # 10 minutes to complete the round-trip


def _external_base(request: Request, settings: Settings) -> str:
    """Scheme+host the browser used, honouring Render's proxy headers."""
    if settings.auth_redirect_base:
        return settings.auth_redirect_base.rstrip("/")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return f"{proto}://{host}"


def _redirect_uri(request: Request, settings: Settings) -> str:
    return f"{_external_base(request, settings)}{settings.api_prefix}/auth/google/callback"


def _is_secure(request: Request, settings: Settings) -> bool:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return proto == "https"


def _require_configured(settings: Settings) -> None:
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="Authentication is disabled.")
    if not (settings.google_oauth_client_id and settings.google_oauth_client_secret
            and settings.session_secret):
        raise HTTPException(status_code=500, detail="OAuth is not configured on the server.")


@router.get("/google/login", summary="Start Google sign-in")
def google_login(request: Request, settings: Settings = Depends(get_settings)):
    _require_configured(settings)
    nonce = secrets.token_urlsafe(16)
    state = sign({"n": nonce}, settings.session_secret, ttl_seconds=_STATE_TTL)
    url = goog.build_authorize_url(
        settings.google_oauth_client_id, _redirect_uri(request, settings), state
    )
    resp = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        _STATE_COOKIE, state, max_age=_STATE_TTL, httponly=True,
        secure=_is_secure(request, settings), samesite="lax", path="/",
    )
    return resp


@router.get("/google/callback", summary="Google OAuth callback")
def google_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    _require_configured(settings)
    if error:
        return RedirectResponse(f"/login?error={error}", status_code=302)
    cookie_state = request.cookies.get(_STATE_COOKIE)
    if not code or not state or state != cookie_state or not verify(state, settings.session_secret):
        return RedirectResponse("/login?error=bad_state", status_code=302)

    try:
        identity = goog.exchange_code(
            code=code,
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
            redirect_uri=_redirect_uri(request, settings),
        )
        user = AuthUserService(db).upsert_from_google(
            identity,
            allowed_domains=settings.allowed_domains_list,
            admin_emails=settings.admin_emails_list,
        )
        db.commit()
    except PermissionError as exc:
        return RedirectResponse(f"/login?error=denied&msg={exc}", status_code=302)
    except ValueError:
        return RedirectResponse("/login?error=oauth_failed", status_code=302)

    token = sign(
        {"uid": user.id, "email": user.email, "role": user.role},
        settings.session_secret,
        ttl_seconds=settings.session_ttl_hours * 3600,
    )
    resp = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        settings.session_cookie_name, token, max_age=settings.session_ttl_hours * 3600,
        httponly=True, secure=_is_secure(request, settings), samesite="lax", path="/",
    )
    resp.delete_cookie(_STATE_COOKIE, path="/")
    return resp


@router.get("/me", summary="Current signed-in user")
def me(
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    return {
        "authenticated": True,
        "auth_enabled": settings.auth_enabled,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_admin": user.is_admin,
            "picture": user.picture,
            # None => all accounts (admin); a list => the manager's scope.
            "account_ids": None if user.allowed_account_ids is None
            else sorted(user.allowed_account_ids),
        },
    }


@router.post("/logout", summary="Sign out")
def logout(request: Request, settings: Settings = Depends(get_settings)) -> Response:
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(settings.session_cookie_name, path="/")
    return resp
