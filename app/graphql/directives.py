from typing import Any

from ariadne import SchemaDirectiveVisitor
from graphql import GraphQLError, default_field_resolver


def _protect(field: Any, check: Any) -> Any:
    original_resolver = field.resolve or default_field_resolver

    def resolver(source: Any, info: Any, **kwargs: Any) -> Any:
        check(info)
        return original_resolver(source, info, **kwargs)

    field.resolve = resolver
    return field


class IsAuthenticatedDirective(SchemaDirectiveVisitor):
    def visit_field_definition(self, field: Any, object_type: Any) -> Any:
        def check(info: Any) -> None:
            if not (info.context or {}).get("user"):
                raise GraphQLError("Authentication required")

        return _protect(field, check)


class IsAdminDirective(SchemaDirectiveVisitor):
    def visit_field_definition(self, field: Any, object_type: Any) -> Any:
        def check(info: Any) -> None:
            user = (info.context or {}).get("user")
            if user is None:
                raise GraphQLError("Authentication required")
            if not user.is_admin:
                raise GraphQLError("Admin only")

        return _protect(field, check)
