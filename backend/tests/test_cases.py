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


def upload(client, headers, data=None, **form):
    return client.post(
        "/api/cases",
        files={"file": ("scan.png", data or png_bytes(), "image/png")},
        data=form,
        headers=headers,
    )


def force_result(monkeypatch, result):
    monkeypatch.setattr(fake_engine, "analyze_image", lambda sha: result)


@pytest.fixture()
def operator_headers(client, make_user):
    make_user(email="op@example.com", role="operator", must_change_password=False)
    return headers_for(client, "op@example.com")


@pytest.fixture()
def clinician_headers(client, make_user):
    make_user(email="doc@example.com", role="clinician", must_change_password=False)
    return headers_for(client, "doc@example.com")


def test_upload_requires_login(client):
    r = client.post("/api/cases", files={"file": ("a.png", png_bytes(), "image/png")})
    assert r.status_code == 401


def test_usable_upload_becomes_graded(client, operator_headers, monkeypatch):
    monkeypatch.setattr(settings, "referable_min_grade", 2)
    force_result(monkeypatch, USABLE)
    r = upload(client, operator_headers)
    assert r.status_code == 202
    case = client.get(f"/api/cases/{r.json()['id']}", headers=operator_headers).json()
    assert case["status"] == "graded"
    assert case["prediction"]["grade"] == 2
    assert case["prediction"]["referable"] is True
    assert case["quality"]["engine_mode"] == "demo_stub"


def test_unusable_upload_has_no_grade(client, operator_headers, monkeypatch):
    force_result(monkeypatch, UNUSABLE)
    r = upload(client, operator_headers)
    case = client.get(f"/api/cases/{r.json()['id']}", headers=operator_headers).json()
    assert case["status"] == "needs_recapture"
    assert case["prediction"] is None


def test_unusable_result_carrying_a_grade_is_rejected(client, operator_headers, monkeypatch):
    force_result(monkeypatch, {**UNUSABLE, "prediction": USABLE["prediction"]})
    r = upload(client, operator_headers)
    case = client.get(f"/api/cases/{r.json()['id']}", headers=operator_headers).json()
    assert case["status"] == "uploaded"
    assert "analysis_error" in case["flags"]
    assert case["prediction"] is None


def test_non_image_is_rejected(client, operator_headers):
    r = client.post(
        "/api/cases",
        files={"file": ("notes.png", b"this is not an image", "image/png")},
        headers=operator_headers,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_image"


def test_small_image_is_rejected(client, operator_headers):
    r = upload(client, operator_headers, data=png_bytes((100, 100)))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "image_too_small"


def test_duplicate_upload_returns_409(client, operator_headers):
    data = png_bytes()
    first = upload(client, operator_headers, data=data)
    second = upload(client, operator_headers, data=data)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "duplicate_image"
    assert second.json()["error"]["details"]["case_id"] == first.json()["id"]


def test_other_users_case_is_hidden_with_404(client, make_user, operator_headers):
    case_id = upload(client, operator_headers).json()["id"]
    make_user(email="op2@example.com", role="operator", must_change_password=False)
    other = headers_for(client, "op2@example.com")
    assert client.get(f"/api/cases/{case_id}", headers=other).status_code == 404


def test_planner_cannot_use_case_routes(client, make_user):
    make_user(email="plan@example.com", role="planner", must_change_password=False)
    r = client.get("/api/cases", headers=headers_for(client, "plan@example.com"))
    assert r.status_code == 403


def test_operator_cannot_review(client, operator_headers, monkeypatch):
    force_result(monkeypatch, USABLE)
    case_id = upload(client, operator_headers).json()["id"]
    r = client.post(
        f"/api/cases/{case_id}/review", json={"decision": "confirm"}, headers=operator_headers
    )
    assert r.status_code == 403


def test_review_flow_confirm(client, operator_headers, clinician_headers, monkeypatch):
    force_result(monkeypatch, USABLE)
    case_id = upload(client, operator_headers).json()["id"]

    r = client.post(f"/api/cases/{case_id}/request-review", headers=operator_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "in_review"

    r = client.post(
        f"/api/cases/{case_id}/review", json={"decision": "confirm"}, headers=clinician_headers
    )
    assert r.status_code == 201
    assert r.json()["status"] == "reviewed"
    assert r.json()["latest_review"]["final_grade"] == 2


def test_override_needs_notes(client, operator_headers, clinician_headers, monkeypatch):
    force_result(monkeypatch, UNUSABLE)
    case_id = upload(client, operator_headers).json()["id"]
    client.post(f"/api/cases/{case_id}/request-review", headers=operator_headers)

    r = client.post(
        f"/api/cases/{case_id}/review",
        json={"decision": "override", "final_grade": 1},
        headers=clinician_headers,
    )
    assert r.status_code == 422

    r = client.post(
        f"/api/cases/{case_id}/review",
        json={"decision": "override", "final_grade": 1, "notes": "Reviewed by clinician"},
        headers=clinician_headers,
    )
    assert r.status_code == 201
    assert r.json()["latest_review"]["final_grade"] == 1


def test_report_has_notice_and_no_patient_reference(client, operator_headers, monkeypatch):
    force_result(monkeypatch, USABLE)
    case_id = upload(client, operator_headers, patient_ref="PAT-777").json()["id"]
    r = client.get(f"/api/cases/{case_id}/report", headers=operator_headers)
    assert r.status_code == 200
    assert r.json()["notice"] == "Decision support only. Not a diagnosis."
    assert "PAT-777" not in r.text