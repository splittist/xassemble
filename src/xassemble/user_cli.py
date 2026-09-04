from __future__ import annotations

import argparse
import getpass
import os
import sqlite3
from collections.abc import Sequence

from .auth import hash_password, normalize_username
from .database import Database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage xassemble user accounts")
    parser.add_argument(
        "--database",
        default=os.environ.get("XASSEMBLE_DB", "data/xassemble.sqlite3"),
        help="SQLite database path (defaults to XASSEMBLE_DB or data/xassemble.sqlite3)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="Create an active user")
    add.add_argument("username")
    add.add_argument("--name", required=True)
    add.add_argument("--admin", action="store_true", help="Create an administrator")
    reset = commands.add_parser("reset-password", help="Set a new password")
    reset.add_argument("username")
    activate = commands.add_parser("activate", help="Activate a user")
    activate.add_argument("username")
    deactivate = commands.add_parser("deactivate", help="Immediately revoke a user's access")
    deactivate.add_argument("username")
    commands.add_parser("list", help="List users")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    database = Database(arguments.database)
    database.initialize()
    try:
        if arguments.command == "add":
            username = normalize_username(arguments.username)
            name = arguments.name.strip()
            if not name:
                raise ValueError("Name is required")
            password_hash = hash_password(_prompt_password())
            role = "admin" if arguments.admin else "member"
            database.create_user(name, username, password_hash, role=role)
            print(f"Created active {role}: {username}")
        elif arguments.command == "reset-password":
            username = normalize_username(arguments.username)
            if not database.update_user_password(
                username, hash_password(_prompt_password()), must_change_password=True
            ):
                raise ValueError(f"User not found: {username}")
            print(f"Password reset: {username}")
        elif arguments.command in {"activate", "deactivate"}:
            username = normalize_username(arguments.username)
            active = arguments.command == "activate"
            if not database.set_user_active(username, active):
                raise ValueError(f"User not found: {username}")
            print(f"{'Activated' if active else 'Deactivated'} user: {username}")
        else:
            for user in database.list_users():
                status = "active" if user["active"] else "inactive"
                print(f"{user['username']}\t{user['name']}\t{status}")
    except (ValueError, sqlite3.IntegrityError) as exc:
        print(f"Error: {exc}")
        return 1
    return 0


def _prompt_password() -> str:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match")
    return password


if __name__ == "__main__":
    raise SystemExit(main())
