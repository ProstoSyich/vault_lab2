import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent

logger = logging.getLogger("vault.audit")


def write_event(
    db: Session,
    event_type: str,
    *,
    actor_id: int | None = None,
    client_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    # Секреты в metadata не попадают: ответственность вызывающего кода.
    event = AuditEvent(
        event_type=event_type,
        actor_id=actor_id,
        client_id=client_id,
        ip=ip,
        user_agent=user_agent,
        metadata_json=metadata,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    logger.info("audit event=%s actor_id=%s", event_type, actor_id)
    return event
