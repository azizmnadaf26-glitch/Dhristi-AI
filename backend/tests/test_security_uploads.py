import io
import os
import re
from pathlib import Path

import pytest
from PIL import Image as PILImage

from app.config import settings, validate_settings

PASSWORD = "Correct-Pass-123"


def login_as(client, make_user, email, role):
    user = make_user(email=email, role=role, must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def random_png(size=(300, 300)):
    img = PILImage.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def upload(client, headers, data, filename="scan.png"):
    return client.post(
        "/api/cases", headers=headers, files={"file": (filename, data, "image/png")}
    )


def case_count(client, headers):
    return client.get("/api/cases", headers=headers).json()["total"]


# ---------- bad uploads ----------

def test_text_file_is_rejected(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    response = upload(client, headers, b"this is not an image")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_image"
    assert case_count(client, headers) == 0


def test_gif_is_rejected(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    buf = io.BytesIO()
    PILImage.new("RGB", (300, 300)).save(buf, format="GIF")
    response = upload(client, headers, buf.getvalue(), "scan.png")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_image_type"


def test_truncated_png_is_rejected(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    data = random_png()
    response = upload(client, headers, data[: len(data) // 2])
    assert response.status_code == 422
    assert case_count(client, headers) == 0


def test_image_over_the_pixel_limit_is_rejected_and_not_stored(
    client, make_user, monkeypatch
):
    monkeypatch.setattr(settings, "max_image_pixels", 1_000_000)
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    buf = io.BytesIO()
    PILImage.new("L", (2000, 2000)).save(buf, format="PNG")  # 4 million pixels, tiny file

    response = upload(client, headers, buf.getvalue())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "image_too_large"
    assert case_count(client, headers) == 0
    originals = Path(settings.storage_dir) / "originals"
    assert not originals.exists() or list(originals.iterdir()) == []


def test_small_image_is_rejected(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    response = upload(client, headers, random_png((100, 100)))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "image_too_small"


# ---------- storage safety ----------

def test_exif_metadata_is_stripped_from_the_stored_image(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    img = PILImage.frombytes("RGB", (300, 300), os.urandom(300 * 300 * 3))
    exif = PILImage.Exif()
    exif[270] = "SECRET-EXIF-TEXT"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    data = buf.getvalue()
    assert b"SECRET-EXIF-TEXT" in data  # sanity check: the upload really had metadata

    case_id = upload(client, headers, data, "photo.jpg").json()["id"]
    image_id = client.get(f"/api/cases/{case_id}", headers=headers).json()["image_id"]
    stored = client.get(f"/api/images/{image_id}/file", headers=headers)

    assert stored.status_code == 200
    assert b"SECRET-EXIF-TEXT" not in stored.content
    assert 270 not in PILImage.open(io.BytesIO(stored.content)).getexif()


def test_stored_filename_is_random_never_the_users(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    response = upload(client, headers, random_png(), "../../evil.png")
    assert response.status_code == 202

    files = list((Path(settings.storage_dir) / "originals").iterdir())
    assert len(files) == 1
    assert re.fullmatch(r"[0-9a-f]{32}\.png", files[0].name)


def test_image_file_is_private_and_not_cached(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    case_id = upload(client, headers, random_png()).json()["id"]
    image_id = client.get(f"/api/cases/{case_id}", headers=headers).json()["image_id"]
    response = client.get(f"/api/images/{image_id}/file", headers=headers)
    assert response.headers["Cache-Control"] == "private, no-store"


def test_another_operator_cannot_fetch_the_image(client, make_user):
    _, headers_a = login_as(client, make_user, "a@example.com", "operator")
    _, headers_b = login_as(client, make_user, "b@example.com", "operator")
    case_id = upload(client, headers_a, random_png()).json()["id"]
    image_id = client.get(f"/api/cases/{case_id}", headers=headers_a).json()["image_id"]

    response = client.get(f"/api/images/{image_id}/file", headers=headers_b)

    assert response.status_code == 404  # 404, not 403: existence is not revealed


# ---------- headers ----------

def test_security_headers_are_present_on_error_responses(client):
    response = client.get("/api/cases")  # no login -> 401
    assert response.status_code == 401
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


# ---------- unsafe configuration is refused at startup ----------

def test_wildcard_cors_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "cors_allowed_origins", "*")
    with pytest.raises(RuntimeError, match="CORS"):
        validate_settings()


def test_production_with_the_fake_engine_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "matlab_fake", True)
    with pytest.raises(RuntimeError, match="Unsafe"):
        validate_settings()


def test_production_with_insecure_cookies_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "matlab_fake", False)
    monkeypatch.setattr(settings, "cookie_secure", False)
    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        validate_settings()


def test_short_jwt_secret_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "too-short")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_settings()


def test_missing_referable_min_grade_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "referable_min_grade", None)
    with pytest.raises(RuntimeError, match="REFERABLE_MIN_GRADE"):
        validate_settings()