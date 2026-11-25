from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from airsense.app.core.config import get_settings
from airsense.app.core.errors import Conflict, Unauthorized, Unprocessable
from airsense.app.core.ratelimit import limiter
from airsense.app.core.security import create_access_token, hash_password, hash_token, new_reset_token, verify_password
from airsense.app.db.models import PasswordResetToken, User, UserPreference, utcnow
from airsense.app.deps import DB, CurrentUser
from airsense.app.schemas import (
    ForgotPasswordIn,
    ForgotPasswordOut,
    LoginIn,
    Message,
    RegisterIn,
    ResetPasswordIn,
    TokenOut,
    UserOut,
)
from airsense.app.services.notify import send_email

router = APIRouter(prefix="/auth", tags=["Authentication"])
_s = get_settings()
# A real hash to compare against when the e-mail is unknown -> constant-time-ish response (no user enumeration)
_DUMMY_HASH = hash_password("dummy-password-123")


def _issue(response: Response, user: User) -> TokenOut:
    token, exp = create_access_token(str(user.id), user.role)
    s = get_settings()
    response.set_cookie(s.cookie_name, token, httponly=True, secure=s.cookie_secure, samesite="lax",
                        max_age=s.access_token_expire_minutes * 60, path="/")
    return TokenOut(access_token=token, expires_at=exp)


def _authenticate(db, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise Unauthorized("Incorrect email or password.")
    if not verify_password(password, user.hashed_password):
        raise Unauthorized("Incorrect email or password.")
    if not user.is_active:
        raise Unauthorized("This account is disabled.")
    user.last_login_at = utcnow()
    db.commit()
    return user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(_s.rate_limit_auth)
def register(request: Request, body: RegisterIn, db: DB):
    if db.scalar(select(User.id).where(User.email == body.email.lower())):
        raise Conflict("An account with this email already exists.")
    user = User(email=body.email.lower(), full_name=body.full_name, hashed_password=hash_password(body.password))
    user.preferences = UserPreference()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
@limiter.limit(_s.rate_limit_auth)
def login(request: Request, response: Response, body: LoginIn, db: DB):
    return _issue(response, _authenticate(db, body.email, body.password))


@router.post("/token", response_model=TokenOut, include_in_schema=True,
             summary="OAuth2 password flow (used by the Swagger 'Authorize' button)")
@limiter.limit(_s.rate_limit_auth)
def token(request: Request, response: Response, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    return _issue(response, _authenticate(db, form.username, form.password))


@router.post("/logout", response_model=Message)
def logout(response: Response):
    response.delete_cookie(get_settings().cookie_name, path="/")
    return Message(message="Signed out.")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.post("/forgot-password", response_model=ForgotPasswordOut, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
def forgot_password(request: Request, body: ForgotPasswordIn, db: DB):
    """Always returns 202 to avoid revealing whether an e-mail is registered."""
    s = get_settings()
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    dev_token = None
    if user is not None and user.is_active:
        plain, hashed = new_reset_token()
        db.add(PasswordResetToken(user_id=user.id, token_hash=hashed,
                                  expires_at=utcnow() + timedelta(minutes=s.password_reset_expire_minutes)))
        db.commit()
        link = f"{s.frontend_url}/reset-password?token={plain}"
        sent = send_email(user.email, "Reset your AirSense password",
                          f"Use this link within {s.password_reset_expire_minutes} minutes:\n{link}\n\n"
                          "If you did not request this, ignore this e-mail.")
        if s.env == "development" and not sent:
            dev_token = plain
    return ForgotPasswordOut(message="If an account exists for that email, a reset link has been sent.",
                             dev_reset_token=dev_token)


@router.post("/reset-password", response_model=Message)
@limiter.limit("10/minute")
def reset_password(request: Request, body: ResetPasswordIn, db: DB):
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(body.token)))
    if row is None or row.used_at is not None or row.expires_at < utcnow():
        raise Unprocessable("This reset link is invalid or has expired.")
    user = db.get(User, row.user_id)
    user.hashed_password = hash_password(body.new_password)
    row.used_at = utcnow()
    db.commit()
    return Message(message="Password updated. You can now sign in.")
