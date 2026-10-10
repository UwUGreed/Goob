import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def engine_for(url=None):
    url = url or os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("DATABASE_URL must use postgresql+psycopg; no SQLite fallback.")
    if os.environ.get("GOOB_ENV") == "production" and "sslmode=verify-full" not in url:
        raise RuntimeError("Production requires PostgreSQL sslmode=verify-full.")
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)
