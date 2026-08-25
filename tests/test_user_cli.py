from xassemble.auth import authenticate
from xassemble.database import Database
from xassemble.user_cli import main

from .auth_helpers import TEST_PASSWORD


def test_user_cli_add_list_deactivate_and_reset_password(tmp_path, monkeypatch, capsys) -> None:
    database_path = tmp_path / "test.sqlite3"
    prompted_passwords = iter([TEST_PASSWORD, TEST_PASSWORD])
    monkeypatch.setattr("xassemble.user_cli.getpass.getpass", lambda _: next(prompted_passwords))

    assert (
        main(
            [
                "--database",
                str(database_path),
                "add",
                "Editor",
                "--name",
                "Test Editor",
            ]
        )
        == 0
    )
    assert "Created active user: editor" in capsys.readouterr().out
    database = Database(database_path)
    assert authenticate(database, "editor", TEST_PASSWORD) is not None

    assert main(["--database", str(database_path), "list"]) == 0
    assert "editor\tTest Editor\tactive" in capsys.readouterr().out
    assert main(["--database", str(database_path), "deactivate", "editor"]) == 0
    assert authenticate(database, "editor", TEST_PASSWORD) is None

    assert main(["--database", str(database_path), "activate", "editor"]) == 0
    new_password = "a different correct password"
    prompted_passwords = iter([new_password, new_password])
    monkeypatch.setattr("xassemble.user_cli.getpass.getpass", lambda _: next(prompted_passwords))
    assert main(["--database", str(database_path), "reset-password", "editor"]) == 0
    assert authenticate(database, "editor", TEST_PASSWORD) is None
    assert authenticate(database, "editor", new_password) is not None
