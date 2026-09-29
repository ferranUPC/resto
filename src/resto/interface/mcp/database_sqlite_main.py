"""Entry point: serve the DatabaseMCP over stdio on a SQLite file (default `resto.db`)."""

from __future__ import annotations

import sys

from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.interface.mcp.database_server import build_server


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "resto.db"
    db = SqliteDatabase(db_path)
    try:
        build_server(db).run()
    finally:
        db.close()


if __name__ == "__main__":
    main()
