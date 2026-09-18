from fastapi.testclient import TestClient

from xassemble.app import create_app
from xassemble.auth import SESSION_COOKIE, authenticate, hash_password
from xassemble.database import Database

from .auth_helpers import TEST_PASSWORD, TEST_SECRET


def _app_with_users(path):
    database = Database(path)
    database.initialize()
    admin = database.create_user(
        "Administrator",
        "admin",
        hash_password(TEST_PASSWORD),
        role="admin",
        must_change_password=False,
    )
    member = database.create_user(
        "Member",
        "member",
        hash_password(TEST_PASSWORD),
        must_change_password=False,
    )
    return create_app(path, secret_key=TEST_SECRET), database, admin, member


def test_first_login_requires_a_password_change(tmp_path) -> None:
    path = tmp_path / "test.sqlite3"
    database = Database(path)
    database.initialize()
    database.create_user("New User", "new-user", hash_password(TEST_PASSWORD))
    app = create_app(path, secret_key=TEST_SECRET)

    with TestClient(app) as client:
        login = client.post(
            "/auth/login", json={"username": "new-user", "password": TEST_PASSWORD}
        )
        assert login.status_code == 200
        assert login.json()["must_change_password"] is True
        assert client.get("/document-sets").status_code == 403
        assert client.get("/document-sets/letters/questionnaire/answer-briefing").status_code == 403
        assert client.post("/document-sets/letters/questionnaire/answer-import").status_code == 403
        assert client.get("/auth/me").status_code == 200
        assert client.post(
            "/auth/change-password",
            json={"current_password": "wrong password", "new_password": "a new secure password"},
        ).status_code == 400
        changed = client.post(
            "/auth/change-password",
            json={"current_password": TEST_PASSWORD, "new_password": "a new secure password"},
        )
        assert changed.status_code == 200
        assert changed.json()["must_change_password"] is False
        assert client.get("/document-sets").status_code == 200
        assert authenticate(database, "new-user", TEST_PASSWORD) is None
        assert authenticate(database, "new-user", "a new secure password") is not None


def test_only_admins_can_manage_users(tmp_path) -> None:
    app, _, _, _ = _app_with_users(tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        client.post("/auth/login", json={"username": "member", "password": TEST_PASSWORD})
        assert client.get("/admin/users").status_code == 403

        client.post("/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        created = client.post(
            "/admin/users",
            json={
                "name": "Second Admin",
                "username": "second.admin",
                "temporary_password": "temporary password",
                "role": "admin",
            },
        )
        assert created.status_code == 201
        assert created.json()["must_change_password"] is True
        assert created.json()["role"] == "admin"
        users = client.get("/admin/users").json()
        assert {user["username"] for user in users} == {"admin", "member", "second.admin"}


def test_admin_reset_revokes_sessions_and_forces_a_change(tmp_path) -> None:
    app, _, _, member = _app_with_users(tmp_path / "test.sqlite3")
    with TestClient(app) as member_client, TestClient(app) as admin_client:
        member_client.post(
            "/auth/login", json={"username": "member", "password": TEST_PASSWORD}
        )
        old_cookie = member_client.cookies.get(SESSION_COOKIE)
        admin_client.post(
            "/auth/login", json={"username": "admin", "password": TEST_PASSWORD}
        )
        reset = admin_client.post(
            f"/admin/users/{member['id']}/reset-password",
            json={"temporary_password": "replacement password"},
        )
        assert reset.status_code == 204
        member_client.cookies.set(SESSION_COOKIE, old_cookie)
        assert member_client.get("/auth/me").status_code == 401
        login = member_client.post(
            "/auth/login", json={"username": "member", "password": "replacement password"}
        )
        assert login.json()["must_change_password"] is True


def test_final_active_admin_cannot_be_deactivated_or_demoted(tmp_path) -> None:
    app, _, admin, _ = _app_with_users(tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        client.post("/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
        for role, active in (("admin", False), ("member", True)):
            response = client.put(
                f"/admin/users/{admin['id']}",
                json={"name": "Administrator", "role": role, "active": active},
            )
            assert response.status_code == 409
            assert "final active administrator" in response.json()["detail"]
