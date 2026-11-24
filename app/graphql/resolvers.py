import logging
from datetime import datetime
from uuid import uuid4

from ariadne import MutationType, ObjectType, QueryType, convert_kwargs_to_snake_case
from graphql import GraphQLError
from sqlalchemy import select

from app.audit.service import write_event
from app.auth.service import EmailAlreadyRegisteredError, register_user
from app.core.jwt import create_access_token
from app.core.passwords import WeakPasswordError
from app.models.audit_event import AuditEvent
from app.models.oauth_client import OAuthClient
from app.models.user import User

logger = logging.getLogger("vault.graphql")

query = QueryType()
mutation = MutationType()
user_type = ObjectType("User")
client_type = ObjectType("Client")
audit_event_type = ObjectType("AuditEvent")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _user_from_context(info) -> User:
    return info.context["user"]


def _client_meta(info) -> tuple[str | None, str | None]:
    request = info.context.get("request")
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


# --- Query -----------------------------------------------------------------


@query.field("me")
def resolve_me(_, info) -> User:
    return _user_from_context(info)


@query.field("users")
@convert_kwargs_to_snake_case
def resolve_users(_, info, search: str | None = None, limit: int = 50, offset: int = 0) -> list[User]:
    db = info.context["db"]
    stmt = select(User).order_by(User.id)
    if search:
        stmt = stmt.where(User.email.ilike(f"%{search}%"))
    stmt = stmt.offset(max(offset, 0)).limit(max(min(limit, 200), 1))
    return list(db.scalars(stmt))


@query.field("clients")
def resolve_clients(_, info) -> list[OAuthClient]:
    db = info.context["db"]
    return list(db.scalars(select(OAuthClient).order_by(OAuthClient.id)))


@query.field("auditEvents")
@convert_kwargs_to_snake_case
def resolve_audit_events(_, info, event_type: str | None = None, limit: int = 50, offset: int = 0):
    db = info.context["db"]
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    stmt = stmt.offset(max(offset, 0)).limit(max(min(limit, 200), 1))
    return list(db.scalars(stmt))


# --- Mutation --------------------------------------------------------------


@mutation.field("registerUser")
@convert_kwargs_to_snake_case
def resolve_register_user(_, info, email: str, password: str) -> dict[str, str]:
    db = info.context["db"]
    ip, user_agent = _client_meta(info)

    try:
        user = register_user(db, email, password, ip=ip, user_agent=user_agent)
    except EmailAlreadyRegisteredError as exc:
        raise GraphQLError(str(exc), extensions={"code": "EMAIL_TAKEN"}) from exc
    except WeakPasswordError as exc:
        raise GraphQLError(str(exc), extensions={"code": "WEAK_PASSWORD"}) from exc

    return {
        "accessToken": create_access_token(user.email),
        "tokenType": "bearer",
    }


@mutation.field("createClient")
@convert_kwargs_to_snake_case
def resolve_create_client(_, info, name: str, is_confidential: bool = False) -> OAuthClient:
    db = info.context["db"]
    user = _user_from_context(info)
    ip, user_agent = _client_meta(info)

    client = OAuthClient(
        client_id=uuid4().hex,
        name=name,
        is_confidential=is_confidential,
        redirect_uris=[],
    )
    db.add(client)
    db.flush()

    write_event(
        db,
        "client.created",
        actor_id=user.id,
        client_id=client.client_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"name": name, "is_confidential": is_confidential},
    )
    logger.info("client created id=%s by user id=%s", client.client_id, user.id)
    return client


@mutation.field("disableUser")
@convert_kwargs_to_snake_case
def resolve_disable_user(_, info, user_id: str) -> User:
    db = info.context["db"]
    actor = _user_from_context(info)
    ip, user_agent = _client_meta(info)

    try:
        target_id = int(user_id)
    except (TypeError, ValueError) as exc:
        raise GraphQLError("User not found") from exc

    target = db.get(User, target_id)
    if target is None:
        raise GraphQLError("User not found")

    target.is_active = False
    db.add(target)

    write_event(
        db,
        "user.disabled",
        actor_id=actor.id,
        ip=ip,
        user_agent=user_agent,
        metadata={"target_user_id": target.id, "email": target.email},
    )
    logger.info("user id=%s disabled by admin id=%s", target.id, actor.id)
    db.refresh(target)
    return target


# --- Типы ------------------------------------------------------------------


@user_type.field("isActive")
def resolve_user_is_active(user: User, _info) -> bool:
    return user.is_active


@user_type.field("isAdmin")
def resolve_user_is_admin(user: User, _info) -> bool:
    return user.is_admin


@user_type.field("createdAt")
def resolve_user_created_at(user: User, _info) -> str | None:
    return _iso(user.created_at)


@client_type.field("clientId")
def resolve_client_id(client: OAuthClient, _info) -> str:
    return client.client_id


@client_type.field("isConfidential")
def resolve_client_is_confidential(client: OAuthClient, _info) -> bool:
    return client.is_confidential


@client_type.field("redirectUris")
def resolve_client_redirect_uris(client: OAuthClient, _info) -> list[str]:
    return client.redirect_uris or []


@client_type.field("createdAt")
def resolve_client_created_at(client: OAuthClient, _info) -> str | None:
    return _iso(client.created_at)


@audit_event_type.field("eventType")
def resolve_audit_event_type(event, _info) -> str:
    return event.event_type


@audit_event_type.field("actorId")
def resolve_audit_actor_id(event, _info) -> str | None:
    return str(event.actor_id) if event.actor_id is not None else None


@audit_event_type.field("userAgent")
def resolve_audit_user_agent(event, _info) -> str | None:
    return event.user_agent


@audit_event_type.field("metadata")
def resolve_audit_metadata(event, _info) -> dict | None:
    return event.metadata_json


@audit_event_type.field("createdAt")
def resolve_audit_created_at(event, _info) -> str | None:
    return _iso(event.created_at)
