import io
import os

import pytest
from PIL import Image as PILImage

from app.config import settings
from app.models.case import Image
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
    """The engine returns these results one after another."""
    it = iter(results)
    monkeypatch.setattr(fake_engine, "analyze_image", lambda sha: next(it))


def upload(client, headers, data=None):
    return client.post(
        "/api/cases",
        files={"file": ("scan.png", data or png_bytes(), "image/png")},
        headers=headers,
    )


def recapture(client, headers, case_id, data=None):
    return client.post(
        f"/api/cases/{case_id}/recapture",
        files={"file": ("again.png", data or png_bytes(), "image/png")},
        headers=headers,
    )


@pytest.fixture()
def operator_headers(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "referable_min_grade", 2)
    make_user(email="op@example.com", role="operator", must_change_password=False)
    return headers_for(client, "op@example.com")


def test_retake_replaces_unusable_image(client, operator_headers, db_session, monkeypatch):
    sequence(monkeypatch, UNUSABLE, USABLE)
    case_id = upload(client, operator_headers).json()["id"]
    first = client.get(f"/api/cases/{case_id}", headers=operator_headers).json()
    assert first["status"] == "needs_recapture"

    assert recapture(client, operator_headers, case_id).status_code == 202

    second = client.get(f"/api/cases/{case_id}", headers=operator_headers).json()
    assert second["status"] == "graded"
    assert second["image_id"] != first["image_id"]
    assert second["prediction"]["grade"] == 2

    # The new image points back at the old one, and the old one is kept.
    assert db_session.get(Image, second["image_id"]).source_image_id == first["image_id"]
    old = client.get(f"/api/images/{first['image_id']}/file", headers=operator_headers)
    assert old.status_code == 200


def test_cannot_retake_a_graded_case(client, operator_headers, monkeypatch):
    sequence(monkeypatch, USABLE)
    case_id = upload(client, operator_headers).json()["id"]
    r = recapture(client, operator_headers, case_id)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invalid_status"


def test_retake_of_other_users_case_is_404(client, make_user, operator_headers, monkeypatch):
    sequence(monkeypatch, UNUSABLE)
    case_id = upload(client, operator_headers).json()["id"]
    make_user(email="op2@example.com", role="operator", must_change_password=False)
    other = headers_for(client, "op2@example.com")
    assert recapture(client, other, case_id).status_code == 404


def test_retake_with_identical_image_is_409(client, operator_headers, monkeypatch):
    sequence(monkeypatch, UNUSABLE)
    data = png_bytes()
    case_id = upload(client, operator_headers, data=data).json()["id"]
    r = recapture(client, operator_headers, case_id, data=data)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "duplicate_image"