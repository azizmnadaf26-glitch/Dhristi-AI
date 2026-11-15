import pytest

from app.config import settings
from app.services.evaluation_import import import_evaluation

PASSWORD = "Correct-Pass-123"
LATEST = "/api/evaluation/latest"
RUNS = "/api/evaluation/runs"
MODELS = "/api/admin/models"


def login_as(client, make_user, email, role):
    user = make_user(email=email, role=role, must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def _payload(split="test", run_at="2026-10-01T12:00:00Z", count=40, version="demo-v1"):
    return {
        "model_version": {"kind": "grading", "version": version},
        "dataset": {"name": "demo-set"},
        "split": split,
        "run_at": run_at,
        "sample_count": count,
        "metrics": {"accuracy": 0.82},
    }


def test_unauthenticated_requests_are_refused(client):
    for url in (LATEST, RUNS, MODELS):
        assert client.get(url).status_code == 401


def test_operator_is_forbidden_everywhere(client, make_user):
    _, headers = login_as(client, make_user, "op@example.com", "operator")
    for url in (LATEST, RUNS, MODELS):
        assert client.get(url, headers=headers).status_code == 403


def test_clinician_planner_admin_can_read_evaluation(client, make_user):
    for role in ("clinician", "planner", "admin"):
        _, headers = login_as(client, make_user, f"{role}@example.com", role)
        assert client.get(LATEST, headers=headers).status_code == 200
        assert client.get(RUNS, headers=headers).status_code == 200


def test_latest_is_empty_without_data(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    body = client.get(LATEST, headers=headers).json()
    assert body["items"] == []
    assert "Not a measured clinical result" in body["label"]


def test_latest_returns_newest_run_per_split(client, make_user, db_session):
    import_evaluation(db_session, _payload(split="test", run_at="2026-10-01T12:00:00Z", count=40))
    import_evaluation(db_session, _payload(split="test", run_at="2026-10-05T09:30:00Z", count=55))
    import_evaluation(db_session, _payload(split="validation", run_at="2026-09-20T08:00:00Z", count=30))
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")

    items = client.get(LATEST, headers=headers).json()["items"]

    assert [i["split"] for i in items] == ["validation", "test"]
    test_item = items[1]
    assert test_item["sample_count"] == 55
    assert test_item["run_at"] == "2026-10-05T09:30:00Z"
    assert test_item["metrics"] == {"accuracy": 0.82}
    assert test_item["is_demo"] is True
    assert test_item["model_version"]["version"] == "demo-v1"


def test_targets_are_settings_only(client, make_user, db_session, monkeypatch):
    import_evaluation(db_session, _payload())
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")

    monkeypatch.setattr(settings, "evaluation_targets", {})
    assert client.get(LATEST, headers=headers).json()["targets"] == {}

    monkeypatch.setattr(settings, "evaluation_targets", {"accuracy": 0.8})
    body = client.get(LATEST, headers=headers).json()
    assert body["targets"] == {"accuracy": 0.8}
    text = str(body).lower()
    for word in ("pass", "fail", "probability"):
        assert word not in text


def test_runs_are_paginated_and_filterable(client, make_user, db_session):
    for day in range(1, 4):
        import_evaluation(db_session, _payload(run_at=f"2026-10-0{day}T12:00:00Z"))
    import_evaluation(db_session, _payload(split="validation", run_at="2026-10-04T12:00:00Z"))
    _, headers = login_as(client, make_user, "plan@example.com", "planner")

    everything = client.get(RUNS, headers=headers).json()
    assert everything["total"] == 4
    assert everything["page"] == 1
    assert everything["page_size"] == 25

    only_test = client.get(RUNS, headers=headers, params={"split": "test"}).json()
    assert only_test["total"] == 3
    assert only_test["items"][0]["run_at"] == "2026-10-03T12:00:00Z"  # newest first

    page2 = client.get(RUNS, headers=headers, params={"page": 2, "page_size": 2}).json()
    assert len(page2["items"]) == 2
    assert page2["page"] == 2


def test_bad_query_values_are_422(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    bad = client.get(RUNS, headers=headers, params={"split": "holdout"})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "validation_error"
    assert client.get(RUNS, headers=headers, params={"page_size": 101}).status_code == 422
    assert client.get(RUNS, headers=headers, params={"page": 0}).status_code == 422


@pytest.mark.parametrize("role", ["clinician", "planner", "operator"])
def test_admin_models_is_admin_only(client, make_user, role):
    _, headers = login_as(client, make_user, f"{role}@example.com", role)
    assert client.get(MODELS, headers=headers).status_code == 403


def test_admin_models_lists_versions(client, make_user, db_session):
    import_evaluation(db_session, _payload(version="demo-v1"))
    import_evaluation(db_session, _payload(version="demo-v2", run_at="2026-10-02T12:00:00Z"))
    _, headers = login_as(client, make_user, "admin@example.com", "admin")

    body = client.get(MODELS, headers=headers).json()

    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 25
    assert [m["version"] for m in body["items"]] == ["demo-v1", "demo-v2"]
    first = body["items"][0]
    assert set(first) == {"id", "kind", "version", "is_active", "notes", "created_at"}
    assert first["is_active"] is False  # imports never activate a model
    assert first["created_at"].endswith("Z")