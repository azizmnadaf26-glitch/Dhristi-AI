import time

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.audit import AuditLog
from app.models.simulation import SimulationRun
from app.schemas.simulation import SIMULATION_LABEL
from app.services import engine_adapter

PASSWORD = "Correct-Pass-123"
VALID = {"weekly_screenings": 200, "devices": 2, "weeks": 12}


def login_as(client, make_user, email, role):
    user = make_user(email=email, role=role, must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def _ok(params):
    return {
        "schema_version": "simulation-1.0",
        "engine_mode": "demo_stub",
        "outputs": {"demo_note": "fixed demo values, not a measured result"},
    }


@pytest.fixture
def use_engine(monkeypatch):
    def _use(fn):
        class _Adapter:
            def run_simulation(self, params):
                return fn(params)

        monkeypatch.setattr(engine_adapter, "get_adapter", lambda: _Adapter())

    return _use


@pytest.fixture(autouse=True)
def _default_engine(use_engine):
    use_engine(_ok)


def test_planner_can_start_simulation(client, make_user):
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    r = client.post("/api/simulations", json=VALID, headers=headers)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    assert body["label"] == SIMULATION_LABEL
    assert body["params"] == VALID
    assert body["result"] is None


def test_run_completes_and_carries_label(client, make_user):
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    sim_id = client.post("/api/simulations", json=VALID, headers=headers).json()["id"]
    r = client.get(f"/api/simulations/{sim_id}", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["label"] == "Simulated estimate, not a measured result"
    assert body["result"]["label"] == SIMULATION_LABEL
    assert body["result"]["outputs"]["demo_note"].startswith("fixed demo values")
    assert body["engine_mode"] == "demo_stub"
    assert body["error_message"] is None
    assert body["started_at"].endswith("Z")
    assert body["finished_at"].endswith("Z")


def test_admin_can_start_simulation(client, make_user):
    _, headers = login_as(client, make_user, "a@example.com", "admin")
    r = client.post("/api/simulations", json=VALID, headers=headers)
    assert r.status_code == 202


def test_operator_cannot_start_simulation(client, make_user):
    _, headers = login_as(client, make_user, "o@example.com", "operator")
    r = client.post("/api/simulations", json=VALID, headers=headers)
    assert r.status_code == 403


def test_clinician_cannot_start_simulation(client, make_user):
    _, headers = login_as(client, make_user, "c@example.com", "clinician")
    r = client.post("/api/simulations", json=VALID, headers=headers)
    assert r.status_code == 403


def test_clinician_can_read_list(client, make_user):
    _, planner = login_as(client, make_user, "p@example.com", "planner")
    client.post("/api/simulations", json=VALID, headers=planner)
    _, clinician = login_as(client, make_user, "c@example.com", "clinician")
    r = client.get("/api/simulations", headers=clinician)
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_operator_cannot_read_simulations(client, make_user):
    _, headers = login_as(client, make_user, "o@example.com", "operator")
    assert client.get("/api/simulations", headers=headers).status_code == 403


def test_unauthenticated_requests_get_401(client):
    assert client.post("/api/simulations", json=VALID).status_code == 401
    assert client.get("/api/simulations").status_code == 401


def test_unknown_field_returns_422(client, make_user):
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    r = client.post("/api/simulations", json={**VALID, "extra": 1}, headers=headers)
    assert r.status_code == 422


def test_bad_value_returns_422(client, make_user):
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    r = client.post("/api/simulations", json={**VALID, "weeks": 0}, headers=headers)
    assert r.status_code == 422


def test_busy_returns_409(client, make_user, db_session):
    planner, headers = login_as(client, make_user, "p@example.com", "planner")
    db_session.add(SimulationRun(created_by=planner.id, status="running", params=VALID))
    db_session.commit()
    r = client.post("/api/simulations", json=VALID, headers=headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "simulation_busy"


def test_second_run_allowed_after_first_finishes(client, make_user):
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    assert client.post("/api/simulations", json=VALID, headers=headers).status_code == 202
    assert client.post("/api/simulations", json=VALID, headers=headers).status_code == 202


def test_engine_error_marks_run_failed(client, make_user, use_engine, db_session):
    def boom(params):
        raise RuntimeError("secret internal detail")

    use_engine(boom)
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    sim_id = client.post("/api/simulations", json=VALID, headers=headers).json()["id"]
    r = client.get(f"/api/simulations/{sim_id}", headers=headers)
    body = r.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "Simulation failed in the engine."
    assert "secret" not in r.text
    assert body["result"] is None
    actions = db_session.scalars(select(AuditLog.action)).all()
    assert "simulation_failed" in actions


def test_timeout_marks_run_failed(client, make_user, use_engine, monkeypatch):
    def slow(params):
        time.sleep(1)
        return _ok(params)

    use_engine(slow)
    monkeypatch.setattr(settings, "matlab_sim_timeout_s", 0.05)
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    sim_id = client.post("/api/simulations", json=VALID, headers=headers).json()["id"]
    body = client.get(f"/api/simulations/{sim_id}", headers=headers).json()
    assert body["status"] == "failed"
    assert body["error_message"] == "Simulation timed out"


def test_unusable_result_marks_run_failed(client, make_user, use_engine):
    use_engine(lambda params: {"engine_mode": "demo_stub", "outputs": "not an object"})
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    sim_id = client.post("/api/simulations", json=VALID, headers=headers).json()["id"]
    body = client.get(f"/api/simulations/{sim_id}", headers=headers).json()
    assert body["status"] == "failed"
    assert body["error_message"] == "Engine returned an unusable result."
    assert body["result"] is None


def test_started_and_completed_are_audited(client, make_user, db_session):
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    client.post("/api/simulations", json=VALID, headers=headers)
    actions = db_session.scalars(select(AuditLog.action)).all()
    assert "simulation_started" in actions
    assert "simulation_completed" in actions


def test_unknown_simulation_returns_404(client, make_user):
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    assert client.get("/api/simulations/9999", headers=headers).status_code == 404


def test_list_is_paginated_newest_first(client, make_user):
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    for _ in range(3):
        client.post("/api/simulations", json=VALID, headers=headers)
    r = client.get("/api/simulations?page=1&page_size=2", headers=headers)
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["id"] > body["items"][1]["id"]


def test_page_size_over_100_returns_422(client, make_user):
    _, headers = login_as(client, make_user, "p@example.com", "planner")
    assert client.get("/api/simulations?page_size=101", headers=headers).status_code == 422