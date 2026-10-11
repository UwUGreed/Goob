"""Server-only configuration. An explicit demo path always isolates tests."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def database_target():
    if os.environ.get('GOOB_DEMO_DB'):
        return os.environ['GOOB_DEMO_DB']
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    return os.environ.get('DATABASE_URL') or str(ROOT / 'operations/demo.sqlite3')
