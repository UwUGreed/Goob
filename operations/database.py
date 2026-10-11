"""Initialize, inspect, or import the configured database without exposing secrets."""
import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from operations.config import database_target, ROOT
from operations.db import connect, seed, TABLES


def import_sqlite(db, path):
    """Back up and copy a consistent source snapshot; refuse nonempty targets."""
    source = sqlite3.connect(f'{Path(path).resolve().as_uri()}?mode=ro', uri=True)
    backup_dir = ROOT / 'backups'
    backup_dir.mkdir(exist_ok=True, mode=0o700)
    backup = backup_dir / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
    snapshot = sqlite3.connect(backup)
    backup.chmod(0o600)
    try:
        source.backup(snapshot)
        db.execute('BEGIN IMMEDIATE')
        counts = {}
        try:
            if any(db.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone() for table in TABLES):
                raise ValueError('Import requires empty application tables; no records changed.')
            for table in TABLES:
                cursor = snapshot.execute(f'SELECT * FROM {table}')
                columns = ','.join('"'+column[0]+'"' for column in cursor.description)
                rows = cursor.fetchall()
                placeholders = ','.join('?' for _ in cursor.description)
                db.executemany(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})', rows)
                counts[table] = len(rows)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return counts
    finally:
        source.close()
        snapshot.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'check', 'import-sqlite'])
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    if args.command == 'import-sqlite' and not args.source:
        parser.error('--source is required')
    db = connect(database_target(), initialize=args.command != 'check')
    try:
        if args.command == 'init':
            seed(db)
            print('Application schema ready; demo seed is idempotent.')
        elif args.command == 'import-sqlite':
            print('Imported row counts:', import_sqlite(db, args.source))
        else:
            print('Database reachable. Application row counts:',
                  {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in TABLES})
    finally:
        db.close()


if __name__ == '__main__':
    main()
