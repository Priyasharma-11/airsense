from __future__ import annotations

from fastapi import APIRouter, Response, status

from airsense.app.core.config import get_settings
from airsense.app.core.errors import NotFound, Unauthorized
from airsense.app.core.security import hash_password, verify_password
from airsense.app.db.models import Station, UserPreference
from airsense.app.deps import DB, CurrentUser
from airsense.app.schemas import Message, PasswordChangeIn, PreferencesIn, PreferencesOut, UserOut, UserUpdateIn

router = APIRouter(prefix="/users", tags=["Users"])


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdateIn, user: CurrentUser, db: DB):
    if body.full_name:
        user.full_name = " ".join(body.full_name.split())
    db.commit()
    return user


@router.post("/me/password", response_model=Message)
def change_password(body: PasswordChangeIn, user: CurrentUser, db: DB):
    if not verify_password(body.current_password, user.hashed_password):
        raise Unauthorized("Current password is incorrect.")
    user.hashed_password = hash_password(body.new_password)
    db.commit()
    return Message(message="Password changed.")


@router.get("/me/preferences", response_model=PreferencesOut)
def get_preferences(user: CurrentUser, db: DB):
    if user.preferences is None:
        user.preferences = UserPreference()
        db.commit()
    return user.preferences


@router.put("/me/preferences", response_model=PreferencesOut)
def put_preferences(body: PreferencesIn, user: CurrentUser, db: DB):
    if body.default_station_id is not None and db.get(Station, body.default_station_id) is None:
        raise NotFound("Station not found.")
    prefs = user.preferences or UserPreference(user_id=user.id)
    for k, v in body.model_dump().items():
        setattr(prefs, k, v)
    user.preferences = prefs
    db.commit()
    return prefs


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(response: Response, user: CurrentUser, db: DB):
    db.delete(user)
    db.commit()
    response.delete_cookie(get_settings().cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
