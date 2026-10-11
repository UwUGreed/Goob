import pytest
from sqlalchemy import text

from operations.persistence.database import engine_for


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_shared_postgres_url_formats(scheme, monkeypatch):
    monkeypatch.delenv("GOOB_ENV", raising=False)
    engine = engine_for(f"{scheme}://user:p%40ss@localhost/test?sslmode=require")
    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.password == "p@ss"
    assert engine.url.query["sslmode"] == "require"
    engine.dispose()


def test_api_role_override_and_explicit_test_target(monkeypatch):
    monkeypatch.delenv("GOOB_ENV", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://shared@localhost/shared")
    monkeypatch.setenv("GOOB_API_DATABASE_URL", "postgresql://runtime@localhost/runtime")
    engine = engine_for()
    assert engine.url.database == "runtime"
    assert engine.url.query["sslmode"] == "require"
    engine.dispose()
    engine = engine_for("postgresql://test@localhost/isolated")
    assert engine.url.database == "isolated"
    engine.dispose()


def test_cloud_tls_cannot_be_disabled(monkeypatch):
    monkeypatch.delenv("GOOB_ENV", raising=False)
    with pytest.raises(RuntimeError, match="requires TLS"):
        engine_for("postgresql://user@localhost/test?sslmode=disable")


def test_production_ssl_mode_is_parsed_not_substring(monkeypatch):
    monkeypatch.setenv("GOOB_ENV", "production")
    with pytest.raises(RuntimeError, match="verify-full"):
        engine_for(
            "postgresql://user@localhost/test?sslmode=disable&application_name=sslmode=verify-full"
        )
    engine = engine_for(
        "postgresql://user@localhost/test?sslmode=verify-full&sslrootcert=/tmp/ca.pem"
    )
    assert engine.url.query["sslrootcert"] == "/tmp/ca.pem"
    engine.dispose()


def test_v1_sessions_ignore_other_module_search_path(engine):
    url = engine.url.update_query_dict(
        {"options": "-csearch_path=goob_foundation -ctimezone=America/New_York"}
    )
    isolated = engine_for(url.render_as_string(hide_password=False))
    try:
        with isolated.connect() as connection:
            assert connection.scalar(text("SHOW search_path")) == "public, pg_catalog"
            assert connection.scalar(text("SHOW timezone")) == "UTC"
            assert connection.scalar(text("SELECT current_schema()")) == "public"
    finally:
        isolated.dispose()


@pytest.mark.parametrize("value", ["sqlite:///demo.sqlite3", "not-a-url-with-secret"])
def test_invalid_database_does_not_fall_back_or_echo_credentials(value):
    with pytest.raises(RuntimeError) as error:
        engine_for(value)
    assert value not in str(error.value)
