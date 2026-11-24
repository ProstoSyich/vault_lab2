import logging
from pathlib import Path
from typing import Any

from ariadne import ScalarType, load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL

from app.graphql.context import get_context_value
from app.graphql.directives import IsAdminDirective, IsAuthenticatedDirective
from app.graphql.resolvers import audit_event_type, client_type, mutation, query, user_type


class SafeGraphQLLogger:
    """Логирует только сообщение ошибки: стандартный логгер Ariadne включает текст запроса."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("vault.graphql.errors")

    def error(self, error: Exception, *_args: Any, **_kwargs: Any) -> None:
        message = getattr(error, "message", None) or error.__class__.__name__
        self._logger.error("GraphQL error: %s", message)


json_scalar = ScalarType("JSON")


@json_scalar.serializer
def serialize_json(value: Any) -> Any:
    return value


type_defs = load_schema_from_path(str(Path(__file__).parent / "schema.graphql"))

schema = make_executable_schema(
    type_defs,
    query,
    mutation,
    user_type,
    client_type,
    audit_event_type,
    json_scalar,
    directives={
        "isAuthenticated": IsAuthenticatedDirective,
        "isAdmin": IsAdminDirective,
    },
)

graphql_app = GraphQL(
    schema,
    context_value=get_context_value,
    debug=True,
    logger=SafeGraphQLLogger(),
)

