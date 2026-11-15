import io
import os
import threading

import pytest
from PIL import Image as PILImage
from sqlalchemy import select

from app.config import settings
from app.errors import AppError
from app.models.audit import AuditLog
from app.services import engine_adapter
from app.services.job_queue import JobQueue
from app.services.timeouts import JobTimeout, call_with_timeout

PASSWORD = "Correct-Pass-123"


def login_headers(client, make_user):
    make_user(email="doc@example.com", role="clinician", must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": "doc@example.com", "password": PASSWORD}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def upload(client, headers):
    img = PILImage.frombytes("RGB", (300, 300), os.urandom(300 * 300 * 3))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return client.post(
        "/api/cases", headers=headers, files={"file": ("a.png", buf.getvalue(), "image/png")}
    )


# ----- timeout helper -----

def test_call_with_timeout_returns_the_value():
    assert call_with_timeout(lambda: 42, 2) == 42


def test_call_with_timeout_raises_when_too_slow():
    with pytest.raises(JobTimeout):
        call_with_timeout(lambda: threading.Event().wait(2), 0.1)


# ----- queue behaviour (real worker thread) -----

def test_analysis_runs_before_simulation():
    q = JobQueue()
    order = []
    gate, started, done = threading.Event(), threading.Event(), threading.Event()

    def blocker():
        started.set()
        gate.wait(5)

    q.submit_analysis(blocker)
    assert started.wait(5)
    q.submit_simulation(lambda: order.append("simulation"))
    q.submit_analysis(lambda: order.append("analysis"))
    gate.set()
    q.submit_simulation(done.set)
    assert done.wait(5)
    assert order == ["analysis", "simulation"]
    q.shutdown(5)


def test_queue_limit_returns_server_busy(monkeypatch):
    monkeypatch.setattr(settings, "max_waiting_analyses", 2)
    q = JobQueue()
    gate, started = threading.Event(), threading.Event()

    def blocker():
        started.set()
        gate.wait(5)

    q.submit_analysis(blocker)
    assert started.wait(5)
    q.submit_analysis(lambda: None)
    q.submit_analysis(lambda: None)  # two jobs now waiting

    with pytest.raises(AppError) as caught:
        q.check_capacity()
    assert caught.value.status_code == 503
    assert caught.value.code == "server_busy"
    assert "Retry-After" in caught.value.headers
    gate.set()
    q.shutdown(5)


def test_no_new_jobs_after_shutdown():
    q = JobQueue()
    q.start()
    q.shutdown(2)
    with pytest.raises(AppError) as caught:
        q.submit_analysis(lambda: None)
    assert caught.value.status_code == 503


def test_worker_survives_a_failing_job():
    q = JobQueue()
    done = threading.Event()

    def boom():
        raise RuntimeError("job failed")

    q.submit_analysis(boom)
    q.submit_analysis(done.set)
    assert done.wait(5)
    q.shutdown(5)


# ----- through the API -----

def test_engine_timeout_flags_the_case_and_is_not_retried(
    client, make_user, db_session, monkeypatch
):
    calls = []

    class Slow:
        def analyze_image(self, sha):
            calls.append(1)
            threading.Event().wait(2)
            return {}

    monkeypatch.setattr(engine_adapter, "get_adapter", lambda: Slow())
    monkeypatch.setattr(settings, "matlab_job_timeout_s", 0.2)
    headers = login_headers(client, make_user)

    response = upload(client, headers)
    assert response.status_code == 202

    detail = client.get(f"/api/cases/{response.json()['id']}", headers=headers).json()
    assert "analysis_timeout" in detail["flags"]
    assert detail["status"] == "uploaded"
    assert detail["prediction"] is None
    assert detail["quality"] is None
    assert len(calls) == 1  # never retried

    row = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "analysis_failed")
    ).one()
    assert row.detail == "reason=analysis_timeout"


def test_full_queue_refuses_upload_and_creates_no_case(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "max_waiting_analyses", 0)
    headers = login_headers(client, make_user)

    response = upload(client, headers)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "server_busy"
    assert "retry-after" in response.headers
    listing = client.get("/api/cases", headers=headers).json()
    assert listing["total"] == 0