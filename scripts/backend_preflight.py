"""Check deployment settings without printing secrets or changing database records."""

import argparse
import json
import os
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.engine import make_url

from operations.persistence.database import engine_for
from operations.persistence.readiness import check_schema


def https_url(value, origin=False):
    try:
        url = urlsplit(value)
        return bool(
            url.scheme == "https"
            and url.hostname
            and url.port != 0
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
            and (not origin or url.path in ("", "/"))
            and "YOUR_" not in value
        )
    except ValueError:
        return False


def inspect(production=False, online=False):
    checks = []

    def add(name, ok, message):
        checks.append({"check": name, "ok": bool(ok), "detail": message})

    url = os.environ.get("GOOB_API_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    engine = None
    try:
        parsed = make_url(url)
        engine = engine_for(url)
        valid = bool(parsed.host and parsed.database and parsed.username)
        if production:
            valid = valid and parsed.query.get("sslmode") == "verify-full"
        add(
            "database_configuration",
            valid,
            "Use a complete PostgreSQL URL; production requires verify-full.",
        )
    except Exception:
        add("database_configuration", False, "A valid TLS PostgreSQL URL is required.")
    if production:
        add(
            "production_mode",
            os.environ.get("GOOB_ENV") == "production",
            "Set GOOB_ENV=production.",
        )
    for name in ("OIDC_ISSUER", "OIDC_JWKS_URL"):
        add(
            name,
            https_url(os.environ.get(name, "")),
            "A configured HTTPS identity-provider URL is required.",
        )
    audience = os.environ.get("OIDC_AUDIENCE", "")
    add(
        "OIDC_AUDIENCE",
        audience.strip() and "YOUR_" not in audience,
        "Set the API audience configured with your identity provider.",
    )
    origins = [
        value.strip() for value in os.environ.get("ALLOWED_ORIGINS", "").split(",") if value.strip()
    ]
    add(
        "ALLOWED_ORIGINS",
        origins and all(https_url(value, origin=True) for value in origins),
        "List exact HTTPS frontend origins without paths or wildcards.",
    )
    try:
        if online and engine is not None:
            try:
                with engine.connect() as connection:
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    schema = check_schema(connection)
                    tls = connection.scalar(
                        text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
                    )
                    add(
                        "cloud_schema",
                        tls,
                        f"Required schema and {schema['tables']} tables checked over TLS.",
                    )
                    if production:
                        privileged = connection.scalar(
                            text(
                                "SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls "
                                "FROM pg_roles WHERE rolname=current_user"
                            )
                        )
                        owns_tables = connection.scalar(
                            text(
                                "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' "
                                "AND tablename LIKE '%_v1' AND tableowner=current_user)"
                            )
                        )
                        can_edit_ledger = connection.scalar(
                            text(
                                "SELECT has_table_privilege(current_user, 'events_v1', 'UPDATE') "
                                "OR has_table_privilege(current_user, 'events_v1', 'DELETE')"
                            )
                        )
                        add(
                            "runtime_role",
                            not (privileged or owns_tables or can_edit_ledger),
                            "Use a non-owner runtime role with the grants in deploy/backend/grants.sql.",
                        )
            except Exception:
                # Never include driver exception text: it can contain connection details.
                add(
                    "cloud_schema",
                    False,
                    "Database/TLS/schema verification failed. Check connectivity, CA, migrations and grants.",
                )
        elif online:
            add("cloud_schema", False, "Database configuration must be fixed before connecting.")
    finally:
        if engine is not None:
            engine.dispose()
    return {
        "configuration_passed": all(check["ok"] for check in checks),
        "database_checked": online,
        "production_checked": production,
        "checks": checks,
        "still_requires": [
            "Real identity-provider login and authenticated API smoke test",
            "Vultr/HTTPS deployment acceptance",
        ],
        "tbd": ["Gemini", "ElevenLabs"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file", help="Explicit private settings file; existing environment wins"
    )
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--online", action="store_true", help="Read-only cloud schema/TLS check")
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv

        if not os.path.isfile(args.env_file):
            parser.error("Environment file not found.")
        load_dotenv(args.env_file, override=False)
    result = inspect(args.production, args.online)
    print(json.dumps(result, indent=2))
    return 0 if result["configuration_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
