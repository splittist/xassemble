from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from xassemble.app import create_app
from xassemble.auth import hash_password
from xassemble.database import Database

TEST_PASSWORD = "correct horse battery staple"
TEST_SECRET = "test-secret-key-that-is-longer-than-thirty-two-characters"


def authenticated_app(database_path: Path) -> tuple[FastAPI, Database]:
    database = Database(database_path)
    database.initialize()
    database.create_user("Test Editor", "editor", hash_password(TEST_PASSWORD))
    return create_app(database_path, secret_key=TEST_SECRET), database


def log_in(client: TestClient) -> None:
    response = client.post(
        "/auth/login", json={"username": "editor", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
