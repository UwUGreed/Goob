"""Run backend regression tests in isolated cloud schemas and verify app data is unchanged."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import text

from operations.persistence.database import engine_for

ROOT = Path(__file__).resolve().parents[1]


def inventory(engine):
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        tables = connection.execute(
            text(
                "SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN "
                "('goob', 'goob_foundation', 'goob_db_meta', 'public') ORDER BY 1, 2"
            )
        ).all()
        result = {}
        quote = engine.dialect.identifier_preparer.quote_identifier
        for schema, table in tables:
            if schema == "public" and not (table.endswith("_v1") or table == "alembic_version"):
                continue
            checksum, count = hashlib.sha256(), 0
            rows = connection.execute(
                text(
                    f"SELECT to_jsonb(t)::text FROM {quote(schema)}.{quote(table)} t ORDER BY to_jsonb(t)::text"
                )
            )
            for row in rows:
                checksum.update(row[0].encode())
                checksum.update(b"\n")
                count += 1
            result[f"{schema}.{table}"] = {"rows": count, "sha256": checksum.hexdigest()}
        schemas = list(
            connection.scalars(
                text(
                    "SELECT nspname FROM pg_namespace WHERE left(nspname, 10)='goob_test_' ORDER BY nspname"
                )
            )
        )
        return result, schemas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        required=True,
        help="Explicit private file containing the intended test DATABASE_URL",
    )
    args = parser.parse_args()
    if not Path(args.env_file).is_file():
        parser.error("Environment file not found.")
    values = dotenv_values(args.env_file)
    url = values.get("TEST_DATABASE_URL") or values.get("DATABASE_URL")
    if not url:
        parser.error("File must contain TEST_DATABASE_URL or DATABASE_URL.")
    engine = None
    try:
        engine = engine_for(url)
        before, schemas_before = inventory(engine)
        print(
            f"Recorded checksums for {len(before)} application tables; no row data exported.",
            flush=True,
        )
        env = os.environ.copy()
        env["TEST_DATABASE_URL"] = url
        env["GOOB_TEST_POSTGRES_URL"] = engine.url.set(drivername="postgresql").render_as_string(
            hide_password=False
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-c",
                "tests/backend_v1/pytest.ini",
                "tests/backend_v1",
                "tests/test_operations.py",
                "tests/test_cloud_configuration.py",
                "-q",
            ],
            cwd=ROOT,
            env=env,
        )
        after, schemas_after = inventory(engine)
        report = {
            "tests_passed": result.returncode == 0,
            "application_tables_checked": len(before),
            "application_data_unchanged": before == after,
            "test_schema_inventory_unchanged": schemas_before == schemas_after,
            "provider_calls": "mocked; Gemini and ElevenLabs remain TBD",
        }
        print(json.dumps(report, indent=2))
        return (
            0
            if result.returncode == 0 and before == after and schemas_before == schemas_after
            else 1
        )
    except Exception:
        print(
            "Verification could not complete. Check private database settings and test dependencies; connection details are omitted.",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
