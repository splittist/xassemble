import pytest
from fastapi.testclient import TestClient

from xassemble.app import create_app
from xassemble.auth import SESSION_COOKIE, hash_password
from xassemble.database import Database

from .auth_helpers import TEST_PASSWORD, TEST_SECRET, authenticated_app, log_in


def test_all_application_routes_require_a_valid_session(tmp_path) -> None:
    app, _ = authenticated_app(tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/document-sets")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Session"
        assert client.get("/docs").status_code == 401


def test_frontend_shell_is_available_before_login(tmp_path) -> None:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("<h1>xassemble</h1>", encoding="utf-8")
    app = create_app(tmp_path / "test.sqlite3", secret_key=TEST_SECRET, frontend_dist=frontend)
    with TestClient(app) as client:
        assert client.get("/").text == "<h1>xassemble</h1>"
        assert client.get("/sets/nda-pack/assemble").status_code == 200


def test_login_cookie_identity_logout_and_invalid_credentials(tmp_path) -> None:
    app, _ = authenticated_app(tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        bad = client.post(
            "/auth/login", json={"username": "editor", "password": "incorrect-password"}
        )
        assert bad.status_code == 401

        login = client.post(
            "/auth/login", json={"username": "EDITOR", "password": TEST_PASSWORD}
        )
        assert login.status_code == 200
        cookie = login.headers["set-cookie"]
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie
        assert login.json()["username"] == "editor"
        assert "password_hash" not in login.json()
        assert client.get("/auth/me").json()["name"] == "Test Editor"

        assert client.post("/auth/logout").status_code == 204
        assert client.get("/auth/me").status_code == 401


def test_deactivation_revokes_an_existing_cookie_on_the_next_request(tmp_path) -> None:
    app, database = authenticated_app(tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        log_in(client)
        assert client.get("/document-sets").status_code == 200
        assert database.set_user_active("editor", False)
        assert client.get("/document-sets").status_code == 401
        login = client.post(
            "/auth/login", json={"username": "editor", "password": TEST_PASSWORD}
        )
        assert login.status_code == 401


def test_tampered_cookie_is_rejected(tmp_path) -> None:
    app, _ = authenticated_app(tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE, "tampered")
        assert client.get("/document-sets").status_code == 401


def test_passwords_are_argon2_hashed(tmp_path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    user = database.create_user("Editor", "editor", hash_password(TEST_PASSWORD))
    assert user["password_hash"].startswith("$argon2id$")
    assert TEST_PASSWORD not in user["password_hash"]


def test_missing_secret_prevents_application_start(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("XASSEMBLE_SECRET_KEY", raising=False)
    app = create_app(tmp_path / "test.sqlite3", secret_key=None)
    with pytest.raises(RuntimeError, match="XASSEMBLE_SECRET_KEY"), TestClient(app):
        pass
