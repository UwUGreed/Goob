"""Shared database desk and server-only provider integrations."""
import os
from pathlib import Path
import httpx
import hashlib
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from operations.persistence.models import LoginAttempt, now
from fastapi import Body, Depends, Header
from operations.api_v1.portal_auth import register_auth
from operations.domain import desk
from operations.domain.common import Problem, command


def register_portal(app, factory, session, actor):
    register_auth(app, factory)

    def provider_limit(user, provider, limit):
        key = hashlib.sha256((provider+":"+user.tenant+":"+user.subject).encode()).hexdigest()
        with factory() as db:
            db.execute(insert(LoginAttempt).values(key=key, attempts=0, window_start=now()).on_conflict_do_nothing())
            bucket = db.scalar(select(LoginAttempt).where(LoginAttempt.key == key).with_for_update())
            if bucket.window_start < now()-timedelta(hours=1):
                bucket.window_start, bucket.attempts = now(), 0
            if bucket.attempts >= limit:
                raise Problem("Provider request allowance exhausted. Try again later.", 429)
            bucket.attempts += 1
            db.commit()

    @app.get("/api/config")
    def configuration(db=Depends(session), user=Depends(actor)):
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / "goob-dispatch" / ".env.local", override=False)
        return {"authenticated": True, "localDemo": False, "databaseBacked": True, "browserKey": os.environ.get("GOOGLE_MAPS_BROWSER_KEY", ""), "mapId": os.environ.get("GOOGLE_MAP_ID", ""), "routes": bool(os.environ.get("GOOGLE_MAPS_SERVER_KEY")), "voice": bool(os.environ.get("ELEVENLABS_API_KEY"))}

    @app.get("/api/dispatch")
    def dispatch_state(db=Depends(session), user=Depends(actor)):
        return {"state": desk.snapshot(db, user)}

    @app.post("/api/dispatch")
    def dispatch_command(body: dict = Body(...), idempotency_key: str = Header(default=""), db=Depends(session), user=Depends(actor)):
        value = command(db, user, idempotency_key, "portal.dispatch", body, lambda: desk.run(db, user, body))
        db.commit()
        return {"state": value}

    @app.post("/api/scribe-token")
    def voice_token(user=Depends(actor)):
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise Problem("Voice is not configured. Use a typed request.", 503)
        provider_limit(user, "scribe", 30)
        try:
            result = httpx.post("https://api.elevenlabs.io/v1/single-use-token/realtime_scribe", headers={"xi-api-key": key}, timeout=8)
            result.raise_for_status()
            return {"token": result.json()["token"]}
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise Problem("Voice transcription could not be authorized. Use a typed request.", 502) from exc

    @app.post("/api/routes")
    def driving_route(body: dict = Body(...), user=Depends(actor)):
        key = os.environ.get("GOOGLE_MAPS_SERVER_KEY")
        if not key:
            raise Problem("Google driving routes are not configured. Use the simulated district map.", 503)
        points = []
        for field in ["origin", "destination"]:
            p = body.get(field, {})
            if not isinstance(p, dict) or type(p.get("lat")) not in {int, float} or type(p.get("lng")) not in {int, float} or not 33.96 < p["lat"] < 34.06 or not -81.1 < p["lng"] < -80.98:
                raise Problem("Use a valid route location within the Columbia demo district.", 422)
            points.append({"location": {"latLng": {"latitude": p["lat"], "longitude": p["lng"]}}})
        options = body.get("options", {})
        if not isinstance(options, dict) or any(k not in {"avoidTolls", "avoidHighways", "avoidFerries"} or type(v) is not bool for k, v in options.items()):
            raise Problem("Unsupported routing options.", 422)
        provider_limit(user, "routes", 120)
        try:
            result = httpx.post("https://routes.googleapis.com/directions/v2:computeRoutes", headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline"}, json={"origin": points[0], "destination": points[1], "travelMode": "DRIVE", "routingPreference": "TRAFFIC_UNAWARE", "polylineQuality": "HIGH_QUALITY", "routeModifiers": options}, timeout=10)
            result.raise_for_status()
            r = result.json()["routes"][0]
            return {"encodedPolyline": r["polyline"]["encodedPolyline"], "distanceMeters": r["distanceMeters"], "durationSeconds": float(r["duration"].removesuffix("s"))}
        except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
            raise Problem("Google route request failed. Use the simulated district map.", 502) from exc
