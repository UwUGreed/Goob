"""Vultr-only schema deployment and deliberate website seed. Never loads local .env."""
import os
from pathlib import Path
import subprocess
import sys
from dotenv import dotenv_values
from psycopg2.extensions import parse_dsn


def validate_target(values):
    expected = tuple(values.get(key, '') for key in
                     ('TIGER_DB_HOST', 'TIGER_DB_PORT', 'TIGER_DB_NAME'))
    if not all(expected) or not expected[1].isdigit():
        raise RuntimeError('Set the explicit Tiger Cloud host, numeric port and database name.')
    if expected[0].lower() in ('localhost', '127.0.0.1', '::1'):
        raise RuntimeError('Use the Tiger Cloud endpoint, not a local database.')
    for key in ('DATABASE_URL', 'GOOB_DATABASE_URL'):
        try:
            params = parse_dsn(values.get(key, ''))
        except Exception:
            raise RuntimeError('Invalid database URL; credentials omitted.') from None
        actual = tuple(params.get(key, '') for key in ('host', 'port', 'dbname'))
        if actual != expected:
            raise RuntimeError('Database URL does not match the explicit Tiger Cloud target.')
        if params.get('sslmode') != 'verify-full' or not params.get('sslrootcert'):
            raise RuntimeError('Use verify-full and an explicit trusted CA for Tiger Cloud.')
    if values.get('GOOB_API_DATABASE_URL'):
        raise RuntimeError('Remove API URL override for this shared staging migration.')
    return expected


def main():
    values = dotenv_values('/etc/tiger/tiger.env')
    host, port, database = validate_target(values)
    os.environ.update({k: v for k, v in values.items() if v is not None})
    # Do not inherit a different API migration target from the invoking shell.
    os.environ.pop('GOOB_API_DATABASE_URL', None)
    command = sys.argv[1]
    from operations.config import database_target
    from operations.db import connect, seed
    if command == 'check':
        subprocess.run([sys.executable, '-m', 'operations.database', 'check'], check=True)
    elif command == 'seed':
        if sys.argv[2:] != ['--confirm-fictional-demo']:
            raise RuntimeError('Pass --confirm-fictional-demo to seed the website.')
        db = connect(database_target())
        try:
            seed(db)
        finally:
            db.close()
        print('Website demo seed complete; existing demo tenant is preserved.')
    elif command == 'migrate':
        backup = Path(sys.argv[2])
        # Keep credentials out of process arguments and logs.
        env = dict(os.environ, PGDATABASE=os.environ['DATABASE_URL'])
        subprocess.run(['/usr/lib/postgresql/18/bin/pg_dump', '--format=custom', '--file', str(backup)], env=env, check=True)
        subprocess.run([sys.executable, '-m', 'operations.database', 'init'], check=True)
        subprocess.run([sys.executable, '-m', 'database.cli', 'migrate', '--apply',
                        '--deploy-host', host, '--deploy-database', database], check=True)
        subprocess.run([str(Path(sys.executable).parent / 'alembic'), '-c',
                        'alembic-backend.ini', 'upgrade', 'head'], check=True)
    else:
        raise RuntimeError('Expected check, migrate or seed.')


if __name__ == '__main__':
    # Running scripts/file.py otherwise puts scripts/, not the repository, on sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
