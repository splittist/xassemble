from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import QuestionnaireSchema

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    must_change_password INTEGER NOT NULL DEFAULT 1 CHECK (must_change_password IN (0, 1)),
    session_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_sets (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questionnaire_versions (
    id INTEGER PRIMARY KEY,
    document_set_id INTEGER NOT NULL REFERENCES document_sets(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    docx_blob BLOB NOT NULL,
    parsed_schema_json TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
    uploaded_by TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    UNIQUE(document_set_id, version_no)
);

CREATE UNIQUE INDEX IF NOT EXISTS one_current_questionnaire
ON questionnaire_versions(document_set_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS template_versions (
    id INTEGER PRIMARY KEY,
    document_set_id INTEGER NOT NULL REFERENCES document_sets(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    docx_blob BLOB NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
    uploaded_by TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    UNIQUE(document_set_id, label, version_no)
);

CREATE UNIQUE INDEX IF NOT EXISTS one_current_template_per_label
ON template_versions(document_set_id, label) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS generation_log (
    id INTEGER PRIMARY KEY,
    document_set_id INTEGER NOT NULL REFERENCES document_sets(id),
    questionnaire_version_id INTEGER NOT NULL REFERENCES questionnaire_versions(id),
    template_version_ids TEXT NOT NULL,
    project_code TEXT NOT NULL,
    generated_by TEXT NOT NULL,
    generated_at TEXT NOT NULL
);
"""

REQUIRED_TABLES = {
    "users",
    "document_sets",
    "questionnaire_versions",
    "template_versions",
    "generation_log",
}


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)

    def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def is_healthy(self) -> bool:
        try:
            with self.connect() as connection:
                row = connection.execute("PRAGMA quick_check(1)").fetchone()
                tables = _database_tables(connection)
            return row is not None and row[0] == "ok" and REQUIRED_TABLES <= tables
        except (OSError, sqlite3.Error):
            return False

    def verify(self) -> None:
        _validate_database_file(Path(self.path))

    def backup(self, destination: str | Path) -> Path:
        destination_path = Path(destination)
        if destination_path.resolve() == Path(self.path).resolve():
            raise ValueError("Backup destination must differ from the database path")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = destination_path.with_name(
            f".{destination_path.name}.tmp-{uuid.uuid4().hex}"
        )
        try:
            with self.connect() as source, closing(sqlite3.connect(temporary_path)) as target:
                source.backup(target)
            _validate_database_file(temporary_path)
            os.replace(temporary_path, destination_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return destination_path

    def restore(self, source: str | Path) -> Path:
        source_path = Path(source)
        if not source_path.is_file():
            raise ValueError(f"Backup file not found: {source_path}")
        if source_path.resolve() == Path(self.path).resolve():
            raise ValueError("Restore source must differ from the database path")
        _validate_database_file(source_path)
        database_path = Path(self.path)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = database_path.with_name(
            f".{database_path.name}.restore-{uuid.uuid4().hex}"
        )
        try:
            with (
                closing(sqlite3.connect(source_path)) as backup,
                closing(sqlite3.connect(temporary_path)) as target,
            ):
                backup.backup(target)
            _validate_database_file(temporary_path)
            os.replace(temporary_path, database_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return database_path

    def create_user(
        self,
        name: str,
        username: str,
        password_hash: str,
        role: str = "member",
        must_change_password: bool = True,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO users
                   (name, username, password_hash, role, active, must_change_password, created_at)
                   VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (name, username, password_hash, role, int(must_change_password), _now()),
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, name, username, role, active, must_change_password, created_at
                   FROM users ORDER BY username"""
            ).fetchall()
        return [dict(row) for row in rows]

    def update_user_password(
        self,
        username: str,
        password_hash: str,
        *,
        must_change_password: bool = False,
        invalidate_sessions: bool = True,
    ) -> bool:
        with self.connect() as connection:
            if invalidate_sessions:
                cursor = connection.execute(
                    """UPDATE users
                       SET password_hash = ?, must_change_password = ?,
                           session_version = session_version + 1
                       WHERE username = ?""",
                    (password_hash, int(must_change_password), username),
                )
            else:
                cursor = connection.execute(
                    "UPDATE users SET password_hash = ? WHERE username = ?",
                    (password_hash, username),
                )
        return cursor.rowcount == 1

    def update_user(
        self,
        user_id: int,
        *,
        name: str,
        role: str,
        active: bool,
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                return None
            removes_active_admin = (
                row["role"] == "admin"
                and row["active"]
                and (role != "admin" or not active)
            )
            if removes_active_admin:
                count = connection.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1"
                ).fetchone()[0]
                if count <= 1:
                    raise ValueError("The final active administrator cannot be changed")
            connection.execute(
                """UPDATE users SET name = ?, role = ?, active = ?,
                   session_version = session_version + CASE WHEN active = ? THEN 0 ELSE 1 END
                   WHERE id = ?""",
                (name, role, int(active), row["active"], user_id),
            )
            updated = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(updated)

    def set_user_active(self, username: str, active: bool) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT role, active FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row is None:
                return False
            if row["role"] == "admin" and row["active"] and not active:
                count = connection.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1"
                ).fetchone()[0]
                if count <= 1:
                    raise ValueError("The final active administrator cannot be changed")
            cursor = connection.execute(
                """UPDATE users SET active = ?,
                   session_version = session_version + CASE WHEN active = ? THEN 0 ELSE 1 END
                   WHERE username = ?""",
                (int(active), row["active"], username),
            )
        return cursor.rowcount == 1

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_document_set(self, slug: str, name: str, description: str = "") -> dict[str, Any]:
        now = _now()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO document_sets(slug, name, description, created_at) VALUES (?, ?, ?, ?)",
                (slug, name, description, now),
            )
            row = connection.execute(
                "SELECT * FROM document_sets WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return dict(row)

    def list_document_sets(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT ds.*,
                          q.version_no AS questionnaire_version,
                          COUNT(t.id) AS current_template_count
                   FROM document_sets ds
                   LEFT JOIN questionnaire_versions q
                     ON q.document_set_id = ds.id AND q.is_current = 1
                   LEFT JOIN template_versions t
                     ON t.document_set_id = ds.id AND t.is_current = 1
                   GROUP BY ds.id, q.version_no
                   ORDER BY ds.name"""
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document_set(self, slug: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM document_sets WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None

    def delete_document_set(self, document_set_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM generation_log WHERE document_set_id = ?", (document_set_id,)
            )
            connection.execute("DELETE FROM document_sets WHERE id = ?", (document_set_id,))

    def add_questionnaire(
        self,
        document_set_id: int,
        content: bytes,
        schema: QuestionnaireSchema,
        uploaded_by: str,
        note: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            next_version = connection.execute(
                "SELECT COALESCE(MAX(version_no), 0) + 1 FROM questionnaire_versions "
                "WHERE document_set_id = ?",
                (document_set_id,),
            ).fetchone()[0]
            cursor = connection.execute(
                """INSERT INTO questionnaire_versions
                   (document_set_id, version_no, docx_blob, parsed_schema_json,
                    uploaded_by, uploaded_at, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    document_set_id,
                    next_version,
                    content,
                    json.dumps(schema.to_dict()),
                    uploaded_by,
                    _now(),
                    note,
                ),
            )
            row = connection.execute(
                "SELECT * FROM questionnaire_versions WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return dict(row)

    def add_template(
        self,
        document_set_id: int,
        label: str,
        content: bytes,
        uploaded_by: str,
        note: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            next_version = connection.execute(
                "SELECT COALESCE(MAX(version_no), 0) + 1 FROM template_versions "
                "WHERE document_set_id = ? AND label = ?",
                (document_set_id, label),
            ).fetchone()[0]
            cursor = connection.execute(
                """INSERT INTO template_versions
                   (document_set_id, label, version_no, docx_blob,
                    uploaded_by, uploaded_at, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (document_set_id, label, next_version, content, uploaded_by, _now(), note),
            )
            row = connection.execute(
                "SELECT * FROM template_versions WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return dict(row)

    def publish_questionnaire(self, document_set_id: int, version_id: int) -> None:
        with self.connect() as connection:
            target = connection.execute(
                "SELECT id FROM questionnaire_versions WHERE id = ? AND document_set_id = ?",
                (version_id, document_set_id),
            ).fetchone()
            if target is None:
                raise LookupError("Questionnaire version not found")
            connection.execute(
                "UPDATE questionnaire_versions SET is_current = 0 WHERE document_set_id = ?",
                (document_set_id,),
            )
            connection.execute(
                "UPDATE questionnaire_versions SET is_current = 1 WHERE id = ?", (version_id,)
            )

    def publish_template(self, document_set_id: int, version_id: int) -> None:
        with self.connect() as connection:
            target = connection.execute(
                "SELECT label FROM template_versions WHERE id = ? AND document_set_id = ?",
                (version_id, document_set_id),
            ).fetchone()
            if target is None:
                raise LookupError("Template version not found")
            connection.execute(
                "UPDATE template_versions SET is_current = 0 "
                "WHERE document_set_id = ? AND label = ?",
                (document_set_id, target["label"]),
            )
            connection.execute("UPDATE template_versions SET is_current = 1 WHERE id = ?", (version_id,))

    def get_questionnaire(self, document_set_id: int, version_id: int | None = None) -> dict[str, Any] | None:
        query = "SELECT * FROM questionnaire_versions WHERE document_set_id = ?"
        parameters: tuple[object, ...] = (document_set_id,)
        if version_id is None:
            query += " AND is_current = 1"
        else:
            query += " AND id = ?"
            parameters += (version_id,)
        with self.connect() as connection:
            row = connection.execute(query, parameters).fetchone()
        return dict(row) if row else None

    def get_template(
        self,
        document_set_id: int,
        label: str | None = None,
        version_id: int | None = None,
    ) -> dict[str, Any] | None:
        query = "SELECT * FROM template_versions WHERE document_set_id = ?"
        parameters: tuple[object, ...] = (document_set_id,)
        if version_id is not None:
            query += " AND id = ?"
            parameters += (version_id,)
        else:
            query += " AND label = ? AND is_current = 1"
            parameters += (label,)
        with self.connect() as connection:
            row = connection.execute(query, parameters).fetchone()
        return dict(row) if row else None

    def current_templates(self, document_set_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM template_versions WHERE document_set_id = ? AND is_current = 1",
                (document_set_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_versions(self, document_set_id: int) -> dict[str, list[dict[str, Any]]]:
        public_columns = "id, version_no, is_current, uploaded_by, uploaded_at, note"
        with self.connect() as connection:
            questionnaires = connection.execute(
                f"SELECT {public_columns} FROM questionnaire_versions "
                "WHERE document_set_id = ? ORDER BY version_no DESC",
                (document_set_id,),
            ).fetchall()
            templates = connection.execute(
                f"SELECT {public_columns}, label FROM template_versions "
                "WHERE document_set_id = ? ORDER BY label, version_no DESC",
                (document_set_id,),
            ).fetchall()
        return {
            "questionnaires": [dict(row) for row in questionnaires],
            "templates": [dict(row) for row in templates],
        }

    def log_generation(
        self,
        document_set_id: int,
        questionnaire_version_id: int,
        template_version_ids: list[int],
        project_code: str,
        generated_by: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO generation_log
                   (document_set_id, questionnaire_version_id, template_version_ids,
                    project_code, generated_by, generated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    document_set_id,
                    questionnaire_version_id,
                    json.dumps(template_version_ids),
                    project_code,
                    generated_by,
                    _now(),
                ),
            )


def load_schema(row: dict[str, Any]) -> QuestionnaireSchema:
    return QuestionnaireSchema.from_dict(json.loads(row["parsed_schema_json"]))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_database_file(path: Path) -> None:
    try:
        with closing(sqlite3.connect(path)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            tables = _database_tables(connection)
    except sqlite3.Error as exc:
        raise ValueError(f"Invalid SQLite database: {exc}") from exc
    if result is None or result[0] != "ok":
        detail = result[0] if result else "no result"
        raise ValueError(f"SQLite integrity check failed: {detail}")
    missing = REQUIRED_TABLES - tables
    if missing:
        missing_names = ", ".join(sorted(missing))
        raise ValueError(f"Backup is not an xassemble database; missing tables: {missing_names}")


def _database_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
