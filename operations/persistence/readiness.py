"""Read-only schema contract check shared by health probes and deployment tooling."""

from sqlalchemy import literal, select, text, union_all

from operations.persistence.models import Base

SCHEMA_REVISION = "20261014_view_preferences"


def check_schema(connection):
    versions = list(connection.scalars(text("SELECT version_num FROM alembic_version")))
    if versions != [SCHEMA_REVISION]:
        raise RuntimeError("Database migration revision does not match this release.")
    # LIMIT 0 checks every required column and SELECT grant without reading app data.
    # Only checking tenants would accept a half-applied or damaged migration.
    probes = [
        select(literal(1)).select_from(select(table).limit(0).subquery())
        for table in Base.metadata.sorted_tables
    ]
    connection.execute(union_all(*probes))
    return {"revision": SCHEMA_REVISION, "tables": len(Base.metadata.tables)}
