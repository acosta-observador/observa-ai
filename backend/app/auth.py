"""Autenticação simples: password partilhada (APP_PASSWORD) + cookie de sessão assinado."""
from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from .config import settings

COOKIE = "observa_session"
MAX_AGE = 60 * 60 * 24 * 14
_attempts: Dict[str, List[float]] = defaultdict(list)


def auth_enabled() -> bool:
    return bool(settings.app_password)


def _signer() -> TimestampSigner:
    return TimestampSigner(settings.secret_key, salt="observa-session")


def check_configuration() -> None:
    """Em produção (Render define RENDER=true) recusa arrancar sem APP_PASSWORD."""
    if os.getenv("RENDER") and not settings.app_password:
        raise RuntimeError("APP_PASSWORD tem de estar definida em produção")
    if os.getenv("RENDER") and settings.secret_key == "dev-insecure-change-me":
        raise RuntimeError("SECRET_KEY tem de estar definida em produção")


def login(request: Request, response: Response, password: str) -> None:
    ip = request.client.host if request.client else "?"
    now = time.time()
    _attempts[ip] = [t for t in _attempts[ip] if now - t < 60]
    if len(_attempts[ip]) >= 8:
        raise HTTPException(429, "Demasiadas tentativas. Espera um minuto.")
    _attempts[ip].append(now)
    if not auth_enabled() or not hmac.compare_digest(password.encode(), settings.app_password.encode()):
        raise HTTPException(401, "Password incorreta")
    token = _signer().sign(b"ok").decode()
    response.set_cookie(COOKIE, token, max_age=MAX_AGE, httponly=True, samesite="lax", secure=settings.secure_cookies)


def is_authenticated(request: Request) -> bool:
    if not auth_enabled():
        return True  # modo local/demo sem password
    token = request.cookies.get(COOKIE)
    if not token:
        return False
    try:
        _signer().unsign(token, max_age=MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


def require_auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(401, "Não autenticado")
