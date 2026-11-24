import json

from sqlalchemy import select

from app.core.jwt import decode_token
from app.models.audit_event import AuditEvent

EMAIL = "user@example.com"
PASSWORD = "correct-horse-battery-staple-42"


def register(client, email: str = EMAIL, password: str = PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client, email: str = EMAIL, password: str = PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_register_login_me_flow(client):
    response = register(client)
    assert response.status_code == 201

    body = response.json()
    assert body["token_type"] == "bearer"

    payload = decode_token(body["access_token"])
    assert payload["sub"] == EMAIL
    assert payload["typ"] == "access"
    assert payload["jti"]
    assert payload["iat"] < payload["exp"]

    response = login(client)
    assert response.status_code == 200
    token = response.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"id": 1, "email": EMAIL, "is_admin": False}


def test_me_without_token_returns_401(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_with_invalid_token_returns_401(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_weak_password_not_registered(client, db):
    response = register(client, password="password1234")

    assert response.status_code == 400
    assert "too weak" in response.json()["detail"]
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "user.created")) is None


def test_duplicate_email_returns_409(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 409


def test_wrong_password_returns_neutral_401(client):
    register(client)

    wrong_password = login(client, password="wrong-password-2024!")
    unknown_email = login(client, email="unknown@example.com")

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == "Invalid credentials"
    assert unknown_email.json()["detail"] == "Invalid credentials"


def test_failed_login_audit_has_no_password(client, db):
    register(client)
    login(client, password="wrong-password-2024!")

    event = db.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "user.login.failure")
    )
    assert event is not None
    assert event.metadata_json == {"email": EMAIL}
    assert "password" not in json.dumps(event.metadata_json).lower()


def test_successful_login_writes_audit_event(client, db):
    register(client)
    assert login(client).status_code == 200

    event = db.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "user.login.success")
    )
    assert event is not None
    assert event.actor_id == 1
    assert event.metadata_json == {"email": EMAIL}
    assert event.ip is not None


def test_disabled_user_cannot_login(client, db):
    register(client)

    from app.models.user import User

    user = db.scalar(select(User).where(User.email == EMAIL))
    user.is_active = False
    db.commit()

    assert login(client).status_code == 401
