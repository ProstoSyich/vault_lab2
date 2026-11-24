import logging

from sqlalchemy import select

from app.models.audit_event import AuditEvent

PASSWORD = "correct-horse-battery-staple-42"


def gql(client, query, token=None, variables=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def bearer(admin_headers) -> str:
    return admin_headers["Authorization"].split(" ", 1)[1]


def register_via_rest(client, email="user@example.com", password=PASSWORD) -> str:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201
    return response.json()["access_token"]


def test_me_without_token_is_rejected(client):
    body = gql(client, "{ me { email } }")

    assert body["data"] is None
    assert body["errors"][0]["message"] == "Authentication required"


def test_me_with_token(client):
    token = register_via_rest(client)
    body = gql(client, "{ me { email isActive isAdmin } }", token=token)

    assert body.get("errors") is None
    assert body["data"]["me"] == {
        "email": "user@example.com",
        "isActive": True,
        "isAdmin": False,
    }


def test_users_without_token_is_rejected(client):
    body = gql(client, "{ users { id } }")

    assert body["data"] is None
    assert body["errors"][0]["message"] == "Authentication required"


def test_users_without_admin_rights_is_rejected(client):
    token = register_via_rest(client)
    body = gql(client, "{ users { id } }", token=token)

    assert body["data"] is None
    assert body["errors"][0]["message"] == "Admin only"


def test_admin_can_list_and_search_users(client, admin_headers):
    register_via_rest(client)

    body = gql(client, '{ users(search: "user@") { email isAdmin } }', token=bearer(admin_headers))
    assert body.get("errors") is None
    assert [user["email"] for user in body["data"]["users"]] == ["user@example.com"]

    body = gql(client, '{ users(search: "nobody") { email } }', token=bearer(admin_headers))
    assert body["data"]["users"] == []


def test_register_user_mutation_rejects_weak_password(client):
    body = gql(
        client,
        """
        mutation Register($email: String!, $password: String!) {
          registerUser(email: $email, password: $password) { accessToken tokenType }
        }
        """,
        variables={"email": "new@example.com", "password": "password1234"},
    )

    assert body["data"] is None
    assert "too weak" in body["errors"][0]["message"]
    assert body["errors"][0]["extensions"]["code"] == "WEAK_PASSWORD"


def test_graphql_error_does_not_log_password(client, caplog):
    weak_password = "qwerty12345678"

    with caplog.at_level(logging.ERROR):
        body = gql(
            client,
            f'mutation {{ registerUser(email: "log@example.com", '
            f'password: "{weak_password}") {{ accessToken }} }}',
        )

    assert body["errors"]
    assert "GraphQL error" in caplog.text
    assert weak_password not in caplog.text


def test_register_user_mutation_returns_token(client):
    body = gql(
        client,
        """
        mutation Register($email: String!, $password: String!) {
          registerUser(email: $email, password: $password) { accessToken tokenType }
        }
        """,
        variables={"email": "new@example.com", "password": PASSWORD},
    )

    assert body.get("errors") is None
    assert body["data"]["registerUser"]["tokenType"] == "bearer"
    assert body["data"]["registerUser"]["accessToken"]


def test_create_client_requires_admin(client):
    token = register_via_rest(client)
    body = gql(
        client,
        'mutation { createClient(name: "App") { id } }',
        token=token,
    )

    assert body["data"] is None
    assert body["errors"][0]["message"] == "Admin only"


def test_admin_creates_client_and_audit_event(client, admin_headers, db):
    token = bearer(admin_headers)
    body = gql(
        client,
        """
        mutation Create($name: String!, $isConfidential: Boolean!) {
          createClient(name: $name, isConfidential: $isConfidential) {
            id clientId name isConfidential redirectUris createdAt
          }
        }
        """,
        token=token,
        variables={"name": "Demo App", "isConfidential": True},
    )

    assert body.get("errors") is None
    created = body["data"]["createClient"]
    assert len(created["clientId"]) == 32
    assert created["isConfidential"] is True
    assert created["redirectUris"] == []

    body = gql(client, "{ clients { clientId name } }", token=token)
    assert body["data"]["clients"] == [
        {"clientId": created["clientId"], "name": "Demo App"}
    ]

    event = db.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "client.created")
    )
    assert event is not None
    assert event.client_id == created["clientId"]


def test_admin_disables_user(client, admin_headers, db):
    user_token = register_via_rest(client, email="victim@example.com")
    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {user_token}"}
    ).json()

    body = gql(
        client,
        """
        mutation Disable($id: ID!) {
          disableUser(userId: $id) { id isActive }
        }
        """,
        token=bearer(admin_headers),
        variables={"id": str(me["id"])},
    )

    assert body.get("errors") is None
    assert body["data"]["disableUser"]["isActive"] is False

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 401

    event = db.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "user.disabled")
    )
    assert event is not None
    assert event.metadata_json["target_user_id"] == me["id"]


def test_disable_unknown_user_returns_error(client, admin_headers):
    body = gql(
        client,
        'mutation { disableUser(userId: "999") { id } }',
        token=bearer(admin_headers),
    )

    assert body["data"] is None
    assert body["errors"][0]["message"] == "User not found"
