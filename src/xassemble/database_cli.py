from __future__ import annotations

import argparse
import os
import sqlite3
from collections.abc import Sequence

from .database import Database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Back up and restore the xassemble database")
    parser.add_argument(
        "--database",
        default=os.environ.get("XASSEMBLE_DB", "data/xassemble.sqlite3"),
        help="SQLite database path (defaults to XASSEMBLE_DB or data/xassemble.sqlite3)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup", help="Create a consistent SQLite backup")
    backup.add_argument("destination")
    restore = commands.add_parser("restore", help="Atomically replace the database from a backup")
    restore.add_argument("source")
    restore.add_argument(
        "--confirm-replace",
        action="store_true",
        help="Confirm that the current database may be replaced",
    )
    commands.add_parser("check", help="Run SQLite integrity and schema checks")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    database = Database(arguments.database)
    try:
        if arguments.command == "backup":
            if not os.path.isfile(arguments.database):
                raise ValueError(f"Database file not found: {arguments.database}")
            destination = database.backup(arguments.destination)
            print(f"Backup created: {destination}")
        elif arguments.command == "restore":
            if not arguments.confirm_replace:
                raise ValueError("Restore requires --confirm-replace")
            destination = database.restore(arguments.source)
            print(f"Database restored: {destination}")
        else:
            database.verify()
            print("Database check passed")
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
