import os
import tempfile
from pathlib import Path

# Переменные окружения должны быть выставлены до импорта app.config / app.main.
_TEST_DIR = Path(tempfile.mkdtemp(prefix="vault-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_DIR / 'test.db').as_posix()}"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production"
os.environ["PASSWORD_PEPPER"] = "test-password-pepper-not-for-production"
os.environ["PASSWORD_MIN_LENGTH"] = "12"
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.jwt import create_access_token  # noqa: E402
from app.core.passwords import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Vault-Admin-Passw0rd-2024!"
STRONG_PASSWORD = "correct-horse-battery-staple-42"


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def admin(db) -> User:
    user = User(
        email=ADMIN_EMAIL,
        hashed_password=hash_password(ADMIN_PASSWORD),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_headers(admin) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(admin.email)}"}
