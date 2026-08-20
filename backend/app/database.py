from sqlalchemy import create_engine, inspect, select, text, update
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    hide_parameters=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from . import models  # noqa: F401  ensure models are registered on Base

    Base.metadata.create_all(bind=engine)
    _migrate_legacy_columns()
    _adopt_legacy_goals()


def _migrate_legacy_columns() -> None:
    """Add columns that older databases lack (SQLite has no ALTER ADD IF NOT EXISTS)."""
    tables = set(inspect(engine).get_table_names())
    if "goals" not in tables:
        return
    columns = {column["name"] for column in inspect(engine).get_columns("goals")}
    if "user_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE goals ADD COLUMN user_id INTEGER REFERENCES users(id)"
            ))


def _adopt_legacy_goals() -> None:
    """In local single-user mode, own legacy goals without an owner."""
    if settings.auth_enabled:
        return
    from .models import Goal, User

    with SessionLocal() as session:
        local = session.scalar(select(User).where(User.username == "local"))
        if local is None:
            local = User(username="local", password_hash="")
            session.add(local)
            session.flush()
        session.execute(
            update(Goal).where(Goal.user_id.is_(None)).values(user_id=local.id)
        )
        session.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
