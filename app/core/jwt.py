from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt

from app.config import settings


def create_access_token(sub: str, ttl_min: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    ttl = settings.access_token_ttl_min if ttl_min is None else ttl_min
    payload = {
        "sub": sub,
        "iat": now,
        "exp": now + timedelta(minutes=ttl),
        "jti": uuid4().hex,
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    if payload.get("typ") != "access":
        raise ValueError("Invalid token type")
    if not payload.get("sub"):
        raise ValueError("Token subject is missing")

    return payload
