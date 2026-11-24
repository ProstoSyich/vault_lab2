import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import write_event
from app.core.passwords import hash_password, validate_policy, verify_password
from app.models.user import User

logger = logging.getLogger("vault.auth")


class EmailAlreadyRegisteredError(ValueError):
    pass


def register_user(
    db: Session,
    email: str,
    password: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> User:
    normalized_email = email.strip().lower()

    if db.scalar(select(User.id).where(User.email == normalized_email)) is not None:
        raise EmailAlreadyRegisteredError("Email already registered")

    validate_policy(password, user_inputs=[normalized_email])

    user = User(email=normalized_email, hashed_password=hash_password(password))
    db.add(user)
    db.flush()

    write_event(
        db,
        "user.created",
        actor_id=user.id,
        ip=ip,
        user_agent=user_agent,
        metadata={"email": normalized_email},
    )
    logger.info("user registered id=%s", user.id)
    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> User | None:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))

    if user is None or not verify_password(password, user.hashed_password):
        write_event(
            db,
            "user.login.failure",
            actor_id=user.id if user is not None else None,
            ip=ip,
            user_agent=user_agent,
            metadata={"email": normalized_email},
        )
        logger.warning("login failed for email=%s", normalized_email)
        return None

    if not user.is_active:
        write_event(
            db,
            "user.login.failure",
            actor_id=user.id,
            ip=ip,
            user_agent=user_agent,
            metadata={"email": normalized_email, "reason": "inactive"},
        )
        logger.warning("login attempt for disabled user id=%s", user.id)
        return None

    write_event(
        db,
        "user.login.success",
        actor_id=user.id,
        ip=ip,
        user_agent=user_agent,
        metadata={"email": normalized_email},
    )
    logger.info("login succeeded user id=%s", user.id)
    return user
