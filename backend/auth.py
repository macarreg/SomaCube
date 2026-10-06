"""
Verifies Supabase Auth JWTs on incoming requests.

Local JWKS verification means no network call to Supabase per request, and
no dependency on Supabase's auth service being reachable for tokens already
in the wild. See config.py for the legacy-HS256 fallback.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from functools import wraps
from typing import Optional
from uuid import UUID

import jwt
from flask import request, g, jsonify
from jwt import PyJWKClient

from config import Config
import ssl
import certifi

from sqlalchemy.exc import SQLAlchemyError
from usernames import validate_username

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

logger = logging.getLogger(__name__)

_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{Config.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(
            jwks_url, cache_keys=True, lifespan=3600, ssl_context=_SSL_CONTEXT
        )
    return _jwks_client


def _decode_token(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except Exception as e:
        raise ValueError(f"Malformed token header: {e}")

    alg = header.get("alg", "")

    if alg.startswith("HS"):
        # Legacy project: shared secret, no JWKS endpoint to check.
        if not Config.SUPABASE_JWT_SECRET:
            raise ValueError("Token is HS256-signed but SUPABASE_JWT_SECRET is not configured")
        return jwt.decode(
            token,
            Config.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )

    # Modern Supabase projects sign asymmetrically (RS256/ES256) by default.
    # Deciding by the token's own header — rather than "is SUPABASE_JWT_SECRET
    # set" — means a stale/legacy secret left in .env can't hijack
    # verification for a project that has since moved to asymmetric signing
    # keys, which silently makes every request look anonymous.
    signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience="authenticated",
    )


def _get_claims_from_request() -> Optional[dict]:
    """Decoded JWT claims for this request, or None if missing/invalid.
    Never raises — a missing or invalid token just means "anonymous"."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):].strip()
    if not token:
        return None
    try:
        return _decode_token(token)
    except Exception as e:
        logger.debug(f"Rejected auth token: {e}")
        return None


def get_user_id_from_request() -> Optional[UUID]:
    """The caller's Supabase user id, or None. Never raises — a missing or
    invalid token just means "anonymous", matching today's behavior."""
    claims = _get_claims_from_request()
    if not claims:
        return None
    try:
        return UUID(claims["sub"])
    except Exception as e:
        logger.debug(f"Rejected auth token: {e}")
        return None


def _upsert_user(user_id: UUID, email: Optional[str], desired_username: Optional[str] = None) -> None:
    """Keep the local `users` mirror in sync with the verified token.
    The username is only read when the row is first created (it comes from
    the signup metadata) and is never overwritten afterwards, so manual
    edits in the database stick. Best-effort: never breaks the request."""
    if not email:
        return
    from models import db, User  # local import: avoids a circular import with app.py
    try:
        user = db.session.get(User, user_id)
        if user is None:
            username, _ = validate_username(desired_username)
            try:
                db.session.add(User(id=user_id, email=email, username=username))
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                if username is not None:
                    # Most likely someone claimed the name first. Create the
                    # row without it; the user is prompted to pick another.
                    db.session.add(User(id=user_id, email=email))
                    db.session.commit()
                # else: a concurrent request already created the row
        elif user.email != email:
            user.email = email
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to upsert user {user_id}: {e}")


def load_current_user():
    """Registered as a before_request hook in app.py."""
    claims = _get_claims_from_request()
    if not claims:
        g.user_id = None
        return
    try:
        g.user_id = UUID(claims["sub"])
    except Exception as e:
        logger.debug(f"Rejected auth token: {e}")
        g.user_id = None
        return
    metadata = claims.get("user_metadata") or {}
    _upsert_user(g.user_id, claims.get("email"), metadata.get("username"))


def require_auth(view):
    """Opt a route into '401 if not logged in'. Not used anywhere by default."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if getattr(g, "user_id", None) is None:
            return jsonify({"error": "Authentication required"}), 401
        return view(*args, **kwargs)
    return wrapped


def check_email_exists(email: str) -> Optional[bool]:
    """Best-effort check, via Supabase's Admin API, of whether an account
    with this email already exists. Requires SUPABASE_SERVICE_ROLE_KEY (a
    highly privileged, server-side-only secret — never expose it to the
    frontend). Returns None — never a guessed True/False — if the key isn't
    configured or the request fails for any reason; callers must treat None
    as "couldn't determine" and fall back to a generic message rather than
    presenting it as a definitive answer.

    Note: this endpoint intentionally reveals account existence by email,
    which is normally avoided (see the comment in app.py's /api/auth/*
    routes) — it exists specifically to support the "no account" vs "wrong
    password" login messaging that was requested.
    """
    if not Config.SUPABASE_URL or not Config.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("check_email_exists: SUPABASE_SERVICE_ROLE_KEY is not configured")
        return None
    try:
        query = urllib.parse.urlencode({"email": email})
        url = f"{Config.SUPABASE_URL}/auth/v1/admin/users?{query}"
        req = urllib.request.Request(url, headers={
            "apikey": Config.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {Config.SUPABASE_SERVICE_ROLE_KEY}",
        })
        with urllib.request.urlopen(req, timeout=5, context=_SSL_CONTEXT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        users = body.get("users", [])
        return len(users) > 0
    except Exception as e:
        logger.error(f"check_email_exists failed: {e}")
        return None