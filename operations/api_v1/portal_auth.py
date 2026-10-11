"""Database-backed portal login. OIDC identities remain supported by v1."""
import base64
import hashlib
import hmac
import os
import secrets
from datetime import timedelta

from fastapi import Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from operations.domain.common import Problem
from operations.domain.identity import actor_for
from operations.persistence.models import LoginAttempt, PortalSession, PortalUser, Tenant, now


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1, maxmem=128*1024*1024)
    return "scrypt$32768$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password, encoded):
    try:
        algorithm, cost, salt, expected = encoded.split("$")
        if algorithm != "scrypt" or cost != "32768":
            return False
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt, validate=True), n=32768, r=8, p=1, maxmem=128*1024*1024)
        return hmac.compare_digest(actual, base64.b64decode(expected, validate=True))
    except (ValueError, TypeError):
        return False


# Unknown identifiers do the same expensive verification as known users.
DUMMY_HASH = password_hash(secrets.token_urlsafe(32))


def cookie_name():
    return "__Host-goob_session" if os.environ.get("GOOB_ENV") == "production" else "goob_session"


def session_user(db, request):
    token = request.cookies.get(cookie_name(), "")
    if not token or len(token) > 200:
        raise Problem("Sign in to open your workspace.", 401)
    session = db.get(PortalSession, hashlib.sha256(token.encode()).hexdigest())
    if not session or session.expires_at <= now():
        raise Problem("Your session expired. Sign in again.", 401)
    user = db.get(PortalUser, session.user_id)
    if not user:
        raise Problem("Sign in again.", 401)
    return user, actor_for(db, user.tenant_id, user.subject)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


def register_auth(app, factory):
    def profile(db, user, actor):
        return {"identifier": user.identifier, "userId": user.id, "tenant": actor.tenant, "workspace": db.get(Tenant, actor.tenant).name, "role": actor.role, "demo": user.demo}

    @app.get("/api/auth/session")
    def session(request: Request):
        with factory() as db:
            user, actor = session_user(db, request)
            return profile(db, user, actor)

    @app.post("/api/auth/sign-in")
    def sign_in(body: Login, request: Request, response: Response):
        identifier = body.identifier.strip().casefold()
        with factory() as db:
            # Serialize each bucket without relying on process-local counters.
            keys = [hashlib.sha256(v.encode()).hexdigest() for v in ["user:"+identifier, "ip:"+(request.client.host if request.client else "unknown")]]
            for key in keys:
                db.execute(insert(LoginAttempt).values(key=key, attempts=0, window_start=now()).on_conflict_do_nothing())
                attempt = db.scalar(select(LoginAttempt).where(LoginAttempt.key == key).with_for_update())
                if attempt.window_start < now()-timedelta(minutes=15):
                    attempt.window_start, attempt.attempts = now(), 0
                if attempt.attempts >= (8 if key == keys[0] else 40):
                    db.commit()
                    raise Problem("Too many sign-in attempts. Try again in 15 minutes.", 429)
                attempt.attempts += 1
            user = db.scalar(select(PortalUser).where(PortalUser.identifier == identifier))
            valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
            db.commit()  # Persist failed attempts as well as successful attempts.
            if not user or not valid:
                raise Problem("The identifier or password is incorrect.", 401)
            actor = actor_for(db, user.tenant_id, user.subject)
            # A successful password check clears this user's failed-attempt bucket.
            # The shared IP limit still counts requests to bound resource usage.
            db.get(LoginAttempt, keys[0]).attempts = 0
            old = request.cookies.get(cookie_name(), "")
            if old:
                db.execute(delete(PortalSession).where(PortalSession.token_hash == hashlib.sha256(old.encode()).hexdigest()))
            token = secrets.token_urlsafe(48)
            db.add(PortalSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires_at=now()+timedelta(hours=8)))
            db.commit()
            response.set_cookie(cookie_name(), token, httponly=True, secure=os.environ.get("GOOB_ENV") == "production", samesite="lax", max_age=8*3600, path="/")
            return profile(db, user, actor)

    @app.post("/api/auth/sign-out")
    def sign_out(request: Request, response: Response):
        token = request.cookies.get(cookie_name(), "")
        with factory() as db:
            if token:
                db.execute(delete(PortalSession).where(PortalSession.token_hash == hashlib.sha256(token.encode()).hexdigest()))
                db.commit()
        response.delete_cookie(cookie_name(), path="/", secure=os.environ.get("GOOB_ENV") == "production", httponly=True, samesite="lax")
        return {"signed_out": True}
