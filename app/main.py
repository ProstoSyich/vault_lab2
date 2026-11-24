import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth.router import router as auth_router
from app.config import settings
from app.core.logging import setup_logging
from app.graphql.schema import graphql_app

setup_logging()
logger = logging.getLogger("vault")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("%s started (environment=%s)", settings.app_name, settings.environment)
    yield
    logger.info("%s stopped", settings.app_name)


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.middleware("http")
async def graphql_http_middleware(request: Request, call_next):
    # Без этого Starlette отвечает 307 на /graphql, а часть клиентов теряет Authorization.
    if request.scope["path"] == "/graphql":
        request.scope["path"] = "/graphql/"

    try:
        return await call_next(request)
    finally:
        # Ariadne создаёт сессию в контексте запроса; закрываем её после ответа.
        db = getattr(request.state, "graphql_db", None)
        if db is not None:
            db.close()


app.include_router(auth_router)
app.mount("/graphql", graphql_app)
app.mount("/admin", StaticFiles(directory=STATIC_DIR, html=True), name="admin")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/admin/")
