from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models import User


def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp = str(
            Path(__file__).resolve().parent.parent / ".pytest_tmp"
        )


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    user = User(username="tester", password_hash="test")
    session.add(user)
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    user = db_session.query(User).filter_by(username="tester").one()

    def override_get_db():
        yield db_session

    def override_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
