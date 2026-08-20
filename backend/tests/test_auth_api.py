import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Goal


@pytest.fixture()
def auth_client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_register_creates_user_and_sets_session(auth_client):
    res = auth_client.post(
        "/api/auth/register", json={"username": "alice", "password": "secret123"}
    )
    assert res.status_code == 201
    assert res.json()["username"] == "alice"
    assert "planagent_session" in res.cookies


def test_register_adopts_legacy_goals(db_session, auth_client):
    goal = Goal(title="旧目标", description="", user_id=None)
    db_session.add(goal)
    db_session.commit()

    res = auth_client.post(
        "/api/auth/register", json={"username": "bob", "password": "secret123"}
    )
    assert res.status_code == 201
    db_session.refresh(goal)
    assert goal.user_id == res.json()["id"]


def test_register_duplicate_username(auth_client):
    auth_client.post(
        "/api/auth/register", json={"username": "carol", "password": "secret123"}
    )
    res = auth_client.post(
        "/api/auth/register", json={"username": "carol", "password": "otherpass1"}
    )
    assert res.status_code == 409


def test_login_sets_session_and_me_returns_user(auth_client):
    auth_client.post(
        "/api/auth/register", json={"username": "dave", "password": "secret123"}
    )
    res = auth_client.post(
        "/api/auth/login", json={"username": "dave", "password": "secret123"}
    )
    assert res.status_code == 200
    me = auth_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "dave"


def test_login_wrong_password(auth_client):
    auth_client.post(
        "/api/auth/register", json={"username": "erin", "password": "secret123"}
    )
    res = auth_client.post(
        "/api/auth/login", json={"username": "erin", "password": "wrongpass1"}
    )
    assert res.status_code == 401


def test_logout_clears_session(auth_client):
    auth_client.post(
        "/api/auth/register", json={"username": "frank", "password": "secret123"}
    )
    res = auth_client.post("/api/auth/logout")
    assert res.status_code == 200
    assert auth_client.get("/api/auth/me").status_code == 401


def test_me_requires_login(auth_client):
    assert auth_client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "password": "secret123"},
        {"username": "validname", "password": "short"},
        {"username": "validname", "password": "x" * 129},
    ],
)
def test_invalid_credentials_rejected(auth_client, payload):
    res = auth_client.post("/api/auth/register", json=payload)
    assert res.status_code == 422
