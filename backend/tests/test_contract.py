import io
import json
import os
from pathlib import Path

from PIL import Image as PILImage

from app.main import app

SPEC_FILE = Path(__file__).resolve().parent.parent / "docs" / "contract" / "openapi.json"
PASSWORD = "Correct-Pass-123"
NOTICE = "Decision support only. Not a diagnosis."


def login_as(client, make_user, email, role):
    user = make_user(email=email, role=role, must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def random_png():
    img = PILImage.frombytes("RGB", (300, 300), os.urandom(300 * 300 * 3))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_exported_openapi_matches_the_live_app():
    assert SPEC_FILE.exists(), "Run: python -m scripts.export_openapi"
    saved = json.loads(SPEC_FILE.read_text(encoding="utf-8"))
    live = json.loads(json.dumps(app.openapi()))
    assert saved == live, "docs/contract/openapi.json is out of date. Run: python -m scripts.export_openapi"


def test_api_contract_never_uses_the_word_probability():
    text = json.dumps(app.openapi()).lower()
    assert "probability" not in text


def test_error_responses_have_the_single_standard_shape(client):
    response = client.get("/api/cases")  # no login
    assert response.status_code == 401
    error = response.json()["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_smoke_upload_poll_review_report(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    assert client.get("/api/health").status_code == 200

    upload = client.post(
        "/api/cases",
        headers=headers,
        files={"file": ("scan.png", random_png(), "image/png")},
        data={"patient_ref": "PATIENT-12345", "eye": "left"},
    )
    assert upload.status_code == 202
    case_id = upload.json()["id"]

    detail = client.get(f"/api/cases/{case_id}", headers=headers).json()
    assert detail["status"] in ("graded", "needs_recapture")
    if detail["status"] == "needs_recapture":
        assert detail["prediction"] is None  # quality-first rule

    assert client.post(f"/api/cases/{case_id}/request-review", headers=headers).status_code == 200
    review = client.post(
        f"/api/cases/{case_id}/review", headers=headers, json={"decision": "refer"}
    )
    assert review.status_code == 201

    report = client.get(f"/api/cases/{case_id}/report", headers=headers)
    assert report.status_code == 200
    body = report.json()
    assert body["notice"] == NOTICE
    assert body["latest_review"]["decision"] == "refer"
    assert "PATIENT-12345" not in report.text  # no patient reference in the report