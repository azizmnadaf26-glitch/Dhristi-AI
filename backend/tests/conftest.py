import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app as fastapi_app
from app.models.user import User
from app.routers.cases import get_session_factory
from app.security.hashing import hash_password
from app.security.rate_limit import limiter


class _KeepOpen:
    """Lets the background job share the test session without closing it."""

    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):
        pass


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "storage"))


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_session_factory] = lambda: (
        lambda: _KeepOpen(db_session)
    )
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db_session):
    def _make(email="user@example.com", password="Correct-Pass-123", role="clinician", **extra):
        user = User(email=email, password_hash=hash_password(password), role=role, **extra)
        db_session.add(user)
        db_session.commit()
        return user

    return _make


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def run_jobs_inline(monkeypatch):
    """In tests, background jobs run immediately so results are ready after the request."""
    from app.services import job_queue

    monkeypatch.setattr(job_queue.queue, "inline", True)