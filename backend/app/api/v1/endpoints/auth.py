from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.database.session import get_db
from app.models.user import User
from app.schemas.user import (
    GoogleTokenRequest,
    UserResponse,
    UserUpdate,
    UserMeResponse,
    Token,
)
from app.services.user_service import UserService
from app.utils.security import create_access_token
from app.api.deps import get_current_active_user
from app.core.config import settings

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Google's tokeninfo endpoint performs the signature validation server-side
# at Google. Used as a fallback because some networks return HTTP 403 for
# www.googleapis.com (where google-auth fetches public certificates), while
# oauth2.googleapis.com stays reachable.
_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def _identity_from_claims(claims: dict) -> dict:
    return {
        "sub": str(claims.get("sub", "")),
        "email": str(claims.get("email", "")),
        "name": str(claims.get("name") or claims.get("email", "").split("@")[0]),
        "picture": claims.get("picture"),
    }


def _verify_via_tokeninfo(credential: str) -> dict:
    """Verify an ID token via Google's tokeninfo endpoint (fallback path)."""
    import time

    import httpx

    resp = httpx.get(_TOKENINFO_URL, params={"id_token": credential}, timeout=15.0)
    if resp.status_code != 200:
        raise ValueError(f"tokeninfo rejected token (HTTP {resp.status_code})")

    claims = resp.json()
    if claims.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise ValueError("token audience mismatch")
    iss = str(claims.get("iss", ""))
    if iss not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError(f"token issuer mismatch: {iss}")
    try:
        if int(claims.get("exp", "0")) < time.time():
            raise ValueError("token expired")
    except (TypeError, ValueError):
        raise ValueError("token has invalid expiry")
    if not claims.get("email"):
        raise ValueError("token has no email claim")
    if not claims.get("sub"):
        raise ValueError("token has no sub claim")

    logger.info("Google ID token verified via tokeninfo fallback for %s", claims.get("email"))
    return _identity_from_claims(claims)


def _verify_google_id_token(credential: str):
    """Verify a Google ID token and return identity claims, or None.

    Primary path: google-auth library (fetches Google's public certs from
    www.googleapis.com). Fallback path: tokeninfo endpoint, used when cert
    fetching is blocked on the current network (HTTP 403 / TransportError).
    """
    from google.auth.exceptions import TransportError

    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
        return _identity_from_claims(idinfo)
    except TransportError as e:
        logger.warning(
            "Google certificate fetch failed (%s) — retrying via tokeninfo endpoint", e
        )
        try:
            return _verify_via_tokeninfo(credential)
        except Exception:
            logger.error("tokeninfo fallback also failed", exc_info=True)
            return None


@router.post("/google", response_model=Token)
def google_login(body: GoogleTokenRequest, db: Session = Depends(get_db)):
    idinfo = _verify_google_id_token(body.credential)
    if idinfo is None:
        logger.error("Google token verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    google_id = idinfo["sub"]
    email = idinfo.get("email", "")
    name = idinfo.get("name", email.split("@")[0])
    avatar_url = idinfo.get("picture")

    user_service = UserService(db)
    user = user_service.get_or_create_google_user(
        google_id=google_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
    )

    if not user.is_active:
        logger.warning("Login attempt by inactive user %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    logger.info("User %s logged in via Google", user.id)
    return Token(access_token=access_token)


@router.get("/me", response_model=UserMeResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    logger.debug("User %s retrieved profile", current_user.id)
    return current_user


@router.put("/me", response_model=UserMeResponse)
def update_me(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    user_service = UserService(db)
    updated = user_service.update_user(current_user.id, user_data)
    logger.info("User %s updated profile", current_user.id)
    return updated
