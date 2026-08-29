import sqlite3

from xassemble.database import Database
from xassemble.database_cli import main


def test_backup_and_restore_round_trip(tmp_path, capsys) -> None:
    database_path = tmp_path / "xassemble.sqlite3"
    backup_path = tmp_path / "backups" / "snapshot.sqlite3"
    database = Database(database_path)
    database.initialize()
    database.create_document_set("original", "Original")

    assert main(["--database", str(database_path), "backup", str(backup_path)]) == 0
    assert backup_path.is_file()
    assert "Backup created" in capsys.readouterr().out

    database.create_document_set("later", "Later")
    assert main(["--database", str(database_path), "restore", str(backup_path)]) == 1
    assert "--confirm-replace" in capsys.readouterr().out
    assert (
        main(
            [
                "--database",
                str(database_path),
                "restore",
                str(backup_path),
                "--confirm-replace",
            ]
        )
        == 0
    )
    assert Database(database_path).get_document_set("original") is not None
    assert Database(database_path).get_document_set("later") is None
    assert main(["--database", str(database_path), "check"]) == 0


def test_backup_rejects_non_xassemble_database(tmp_path, capsys) -> None:
    database_path = tmp_path / "xassemble.sqlite3"
    invalid_path = tmp_path / "other.sqlite3"
    Database(database_path).initialize()
    with sqlite3.connect(invalid_path) as connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")

    assert (
        main(
            [
                "--database",
                str(database_path),
                "restore",
                str(invalid_path),
                "--confirm-replace",
            ]
        )
        == 1
    )
    assert "not an xassemble database" in capsys.readouterr().out
