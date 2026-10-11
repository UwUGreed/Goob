import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


def engine_for(url=None):
    # Share the teammate's native PostgreSQL URL while retaining an optional
    # separate runtime-role credential for this service. Never fall back to SQLite.
    value = url or os.environ.get("GOOB_API_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    try:
        parsed = make_url(value)
    except Exception:
        raise RuntimeError("Configure a valid PostgreSQL database URL.") from None
    if parsed.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise RuntimeError("The operations API requires PostgreSQL; no SQLite fallback.")
    parsed = parsed.set(drivername="postgresql+psycopg")
    mode = parsed.query.get("sslmode", "require")
    if mode not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError("Cloud PostgreSQL requires TLS; production requires verify-full.")
    parsed = parsed.update_query_dict({"sslmode": mode})
    if os.environ.get("GOOB_ENV") == "production" and parsed.query.get("sslmode") != "verify-full":
        raise RuntimeError("Production requires PostgreSQL sslmode=verify-full.")
    engine = create_engine(
        parsed,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 10},
    )

    @event.listens_for(engine, "connect")
    def initialize_session(connection, _record):
        # A shared DB role may default to goob or goob_foundation. V1 migrations
        # and queries must always resolve to their own public.*_v1 tables.
        previous = connection.autocommit
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION search_path TO public, pg_catalog")
                cursor.execute("SET TIME ZONE 'UTC'")
        finally:
            connection.autocommit = previous

    return engine


def sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)
