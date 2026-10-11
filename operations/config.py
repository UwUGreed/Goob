"""Server-only cloud PostgreSQL configuration; no local database fallback."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def database_target():
    if os.environ.get('GOOB_DEMO_DB'):
        raise RuntimeError('GOOB_DEMO_DB was removed. Configure an explicit PostgreSQL DATABASE_URL.')
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    value = os.environ.get('DATABASE_URL', '')
    if not value.startswith(('postgres://', 'postgresql://')):
        raise RuntimeError('Configure the cloud PostgreSQL DATABASE_URL in the server environment or .env.')
    return value
