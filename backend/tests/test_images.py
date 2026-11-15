import io
import os
from pathlib import Path

import pytest
from PIL import Image as PILImage

from app.config import settings
from app.models.case import Image

PASSWORD = "Correct-Pass-123"


def png_bytes(size=(300, 300)):
    img = PILImage.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def headers_for(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def operator_headers(client, make_user):
    make_user(email="op@example.com", role="operator", must_change_password=False)
    return headers_for(client, "op@example.com")


def upload_and_get_image_id(client, headers):
    r = client.post(
        "/api/cases",
        files={"file": ("scan.png", png_bytes(), "image/png")},
        headers=headers,
    )
    case = client.get(f"/api/cases/{r.json()['id']}", headers=headers).json()
    return case["image_id"]


def test_owner_can_fetch_image(client, operator_headers):
    image_id = upload_and_get_image_id(client, operator_headers)
    r = client.get(f"/api/images/{image_id}/file", headers=operator_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "private, no-store"
    PILImage.open(io.BytesIO(r.content)).verify()  # it really is an image


def test_image_requires_login(client, operator_headers):
    image_id = upload_and_get_image_id(client, operator_headers)
    assert client.get(f"/api/images/{image_id}/file").status_code == 401


def test_other_users_image_is_hidden_with_404(client, make_user, operator_headers):
    image_id = upload_and_get_image_id(client, operator_headers)
    make_user(email="op2@example.com", role="operator", must_change_password=False)
    other = headers_for(client, "op2@example.com")
    assert client.get(f"/api/images/{image_id}/file", headers=other).status_code == 404


def test_planner_cannot_fetch_images(client, make_user, operator_headers):
    image_id = upload_and_get_image_id(client, operator_headers)
    make_user(email="plan@example.com", role="planner", must_change_password=False)
    r = client.get(f"/api/images/{image_id}/file", headers=headers_for(client, "plan@example.com"))
    assert r.status_code == 403


def test_unknown_image_is_404(client, operator_headers):
    assert client.get("/api/images/9999/file", headers=operator_headers).status_code == 404


def test_path_traversal_is_refused(client, operator_headers, db_session):
    image_id = upload_and_get_image_id(client, operator_headers)

    # A secret file next to (not inside) the originals folder.
    secret = Path(settings.storage_dir) / "secret.txt"
    secret.write_text("top secret")

    image = db_session.get(Image, image_id)
    image.filename = "../secret.txt"
    db_session.commit()

    r = client.get(f"/api/images/{image_id}/file", headers=operator_headers)
    assert r.status_code == 404
    assert "top secret" not in r.text


def test_owner_can_fetch_heatmap(client, operator_headers):
    image_id = upload_and_get_image_id(client, operator_headers)
    heatmaps_dir = Path(settings.storage_dir) / "heatmaps"
    heatmaps_dir.mkdir(parents=True, exist_ok=True)
    heatmap_file = heatmaps_dir / f"{image_id}.png"
    heatmap_file.write_bytes(png_bytes((100, 100)))

    r = client.get(f"/api/images/{image_id}/heatmap", headers=operator_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "private, no-store"
    PILImage.open(io.BytesIO(r.content)).verify()


def test_heatmap_missing_returns_404(client, operator_headers):
    image_id = upload_and_get_image_id(client, operator_headers)
    r = client.get(f"/api/images/{image_id}/heatmap", headers=operator_headers)
    assert r.status_code == 404


def test_heatmap_requires_login(client, operator_headers):
    image_id = upload_and_get_image_id(client, operator_headers)
    assert client.get(f"/api/images/{image_id}/heatmap").status_code == 401


def test_heatmap_other_user_is_hidden(client, make_user, operator_headers):
    image_id = upload_and_get_image_id(client, operator_headers)
    make_user(email="op3@example.com", role="operator", must_change_password=False)
    other = headers_for(client, "op3@example.com")
    assert client.get(f"/api/images/{image_id}/heatmap", headers=other).status_code == 404


def test_planner_cannot_fetch_heatmap(client, make_user, operator_headers):
    image_id = upload_and_get_image_id(client, operator_headers)
    make_user(email="plan2@example.com", role="planner", must_change_password=False)
    r = client.get(f"/api/images/{image_id}/heatmap", headers=headers_for(client, "plan2@example.com"))
    assert r.status_code == 403