"""Read-only comparison of every application record in a source and restored DB."""

import hashlib
import json
import os

from sqlalchemy import select, text

from operations.persistence.database import engine_for
from operations.persistence.models import Base


def digest(connection, table):
    checksum = hashlib.sha256()
    count = 0
    for row in (
        connection.execution_options(stream_results=True)
        .execute(select(table).order_by(*table.primary_key.columns))
        .mappings()
    ):
        checksum.update(
            json.dumps(dict(row), sort_keys=True, default=str, separators=(",", ":")).encode()
        )
        checksum.update(b"\n")
        count += 1
    return count, checksum.hexdigest()


def main():
    source = engine_for(os.environ["SOURCE_DATABASE_URL"])
    restored = engine_for(os.environ["RESTORE_DATABASE_URL"])
    comparisons = []
    with (
        source.connect().execution_options(isolation_level="REPEATABLE READ") as a,
        restored.connect().execution_options(isolation_level="REPEATABLE READ") as b,
    ):
        a.execute(text("SET TRANSACTION READ ONLY"))
        b.execute(text("SET TRANSACTION READ ONLY"))
        for table in Base.metadata.sorted_tables:
            left, right = digest(a, table), digest(b, table)
            comparisons.append(
                {
                    "table": table.name,
                    "source_rows": left[0],
                    "restored_rows": right[0],
                    "matches": left == right,
                }
            )
    print(
        json.dumps(
            {"tables": comparisons, "verified": all(c["matches"] for c in comparisons)}, indent=2
        )
    )
    if not all(c["matches"] for c in comparisons):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
