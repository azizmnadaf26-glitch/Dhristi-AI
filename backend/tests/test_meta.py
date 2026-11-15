import io
import os

import pytest
from PIL import Image as PILImage

from app.config import settings
from app.services import fake_engine

PASSWORD = "Correct-Pass-123"

USABLE = {
    "schema_version": "screening-1.0",
    "engine_mode": "demo_stub",
    "quality": {"verdict": "usable", "reason_codes": []},
    "prediction": {"grade": 2, "class_scores": [0.05, 0.1, 0.7, 0.1, 0.05], "model_score": 0.7},
}
UNUSABLE = {
    "schema_version": "screening-1.0",
    "engine_mode": "demo_stub",
    "quality": {"verdict": "unusable", "reason_codes": ["blurry"]},
    "prediction": None,
}


def png_bytes(size=(300, 300)):
    img = PILImage.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def headers_for(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def sequence(monkeypatch, *results):
    it = iter(results)
    monkeypatch.setattr(fake_engine, "analyze_image", lambda sha: next(it))


@pytest.fixture()
def clinician_headers(client, make_user):
    make_user(email="doc@example.com", role="clinician", must_change_password=False)
    return headers_for(client, "doc@example.com")


@pytest.fixture()
def operator_headers(client, make_user):
    make_user(email="op@example.com", role="operator", must_change_password=False)
    return headers_for(client, "op@example.com")


def test_config_requires_login(client):
    assert client.get("/api/config").status_code == 401


def test_config_returns_only_safe_settings(client, clinician_headers, monkeypatch):
    monkeypatch.setattr(settings, "matlab_fake", True)
    r = client.get("/api/config", headers=clinician_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["notice"] == "Decision support only. Not a diagnosis."
    assert body["engine_mode"] == "demo_stub"
    assert body["limits"]["max_upload_mb"] == settings.max_upload_mb
    assert body["thresholds"]["referable_min_grade"] == settings.referable_min_grade

    text = r.text.lower()
    assert not settings.jwt_secret or settings.jwt_secret.lower() not in text
    for word in ("secret", "database", "password", "token"):
        assert word not in text


def test_summary_requires_allowed_role(client, operator_headers):
    assert client.get("/api/summary").status_code == 401
    assert client.get("/api/summary", headers=operator_headers).status_code == 403


def test_empty_summary_returns_zeros(client, clinician_headers):
    r = client.get("/api/summary", headers=clinician_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_cases"] == 0
    assert all(v == 0 for v in body["by_status"].values())
    assert body["predictions"]["by_grade"] == {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0}
    assert body["flagged_cases"] == 0


def test_planner_can_read_summary(client, make_user):
    make_user(email="plan@example.com", role="planner", must_change_password=False)
    r = client.get("/api/summary", headers=headers_for(client, "plan@example.com"))
    assert r.status_code == 200


def test_summary_counts_and_hides_identifiers(
    client, operator_headers, clinician_headers, monkeypatch
):
    monkeypatch.setattr(settings, "referable_min_grade", 2)
    sequence(monkeypatch, USABLE, USABLE, UNUSABLE)
    for ref in ("PAT-9", None, None):
        client.post(
            "/api/cases",
            files={"file": ("scan.png", png_bytes(), "image/png")},
            data={"patient_ref": ref} if ref else {},
            headers=operator_headers,
        )

    r = client.get("/api/summary", headers=clinician_headers)
    body = r.json()
    assert body["total_cases"] == 3
    assert body["by_status"]["graded"] == 2
    assert body["by_status"]["needs_recapture"] == 1
    assert body["predictions"]["total"] == 2
    assert body["predictions"]["by_grade"]["2"] == 2
    assert body["predictions"]["referable"] == 2
    assert "PAT-9" not in r.text
    assert "case_id" not in r.text


def test_summary_date_range_filters(client, operator_headers, clinician_headers, monkeypatch):
    sequence(monkeypatch, USABLE)
    client.post(
        "/api/cases",
        files={"file": ("scan.png", png_bytes(), "image/png")},
        headers=operator_headers,
    )
    r = client.get(
        "/api/summary?date_from=2000-01-01&date_to=2000-01-02", headers=clinician_headers
    )
    assert r.status_code == 200
    assert r.json()["total_cases"] == 0


def test_summary_rejects_backwards_range(client, clinician_headers):
    r = client.get(
        "/api/summary?date_from=2026-02-01&date_to=2026-01-01", headers=clinician_headers
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"