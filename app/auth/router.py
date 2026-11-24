from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.schemas import Credentials, TokenResponse, UserOut
from app.auth.service import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    register_user,
)
from app.core.deps import get_current_user
from app.core.jwt import create_access_token
from app.core.passwords import WeakPasswordError
from app.db.session import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _request_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    credentials: Credentials,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip, user_agent = _request_meta(request)
    try:
        user = register_user(
            db,
            credentials.email,
            credentials.password,
            ip=ip,
            user_agent=user_agent,
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WeakPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return TokenResponse(access_token=create_access_token(user.email))


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: Credentials,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    ip, user_agent = _request_meta(request)
    user = authenticate_user(
        db,
        credentials.email,
        credentials.password,
        ip=ip,
        user_agent=user_agent,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return TokenResponse(access_token=create_access_token(user.email))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
