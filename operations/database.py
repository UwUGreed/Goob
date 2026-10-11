"""Explicit schema initialization or read-only cloud database inspection."""
import argparse

from operations.config import database_target
from operations.db import TABLES, connect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'check'])
    args = parser.parse_args()
    db = connect(database_target(), initialize=args.command == 'init')
    try:
        if args.command == 'init':
            print('Application schema ready. No records seeded or imported.')
        else:
            print('Cloud database reachable. Application row counts:', {
                table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                for table in TABLES
            })
    finally:
        db.close()


if __name__ == '__main__':
    main()
