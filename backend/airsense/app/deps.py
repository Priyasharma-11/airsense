"""FastAPI dependencies: DB session, current user (Bearer header or httpOnly cookie), role checks."""
from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from airsense.app.core.config import get_settings
from airsense.app.core.errors import Forbidden, Unauthorized
from airsense.app.core.security import decode_access_token
from airsense.app.db.models import User
from airsense.app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def _token_from_request(request: Request, bearer: str | None) -> str | None:
    if bearer:
        return bearer
    return request.cookies.get(get_settings().cookie_name)


def get_current_user_optional(request: Request, db: DB,
                              bearer: Annotated[str | None, Depends(oauth2_scheme)] = None) -> User | None:
    token = _token_from_request(request, bearer)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as e:
        raise Unauthorized("Session expired. Please sign in again.") from e
    except jwt.PyJWTError as e:
        raise Unauthorized("Invalid authentication token.") from e
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise Unauthorized("Account not found or disabled.")
    return user


def get_current_user(user: Annotated[User | None, Depends(get_current_user_optional)]) -> User:
    if user is None:
        raise Unauthorized("Authentication required.")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise Forbidden("Administrator role required.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
AdminUser = Annotated[User, Depends(require_admin)]
