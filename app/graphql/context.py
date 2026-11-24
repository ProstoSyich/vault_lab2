from typing import Any

from app.core.deps import extract_bearer_token, user_from_token
from app.db.session import SessionLocal


async def get_context_value(request: Any, data: Any) -> dict[str, Any]:
    db = SessionLocal()
    # Сессию закрывает middleware в main.py после формирования ответа.
    request.state.graphql_db = db

    token = extract_bearer_token(request.headers.get("authorization"))
    user = user_from_token(db, token) if token else None

    return {"request": request, "db": db, "user": user}
