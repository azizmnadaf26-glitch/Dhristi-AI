import io
import os

import pytest
from PIL import Image as PILImage

from app.config import settings
from app.services import engine_adapter, fake_engine
from app.services.case_service import validate_result
from app.services.engine_adapter import (
    FakeAdapter,
    MatlabAdapter,
    resolve_artifact_path,
)

PASSWORD = "Correct-Pass-123"


def started():
    adapter = FakeAdapter()
    adapter.start()
    return adapter


def test_fake_adapter_matches_the_demo_engine_and_is_deterministic():
    adapter = started()
    sha = "ab12cd34" * 8
    assert adapter.analyze_image(sha) == fake_engine.analyze_image(sha)
    assert adapter.analyze_image(sha) == adapter.analyze_image(sha)


def test_fake_results_pass_the_contract_and_are_labelled_demo():
    adapter = started()
    for i in range(50):
        sha = f"{i * 2654435761 % 2**32:08x}" + "0" * 56
        result = adapter.analyze_image(sha)
        validate_result(result)
        assert result["engine_mode"] == "demo_stub"
        if result["quality"]["verdict"] == "unusable":
            assert result["prediction"] is None


def test_engine_state_lifecycle():
    adapter = FakeAdapter()
    assert adapter.status() == "down"
    with pytest.raises(RuntimeError):
        adapter.analyze_image("a" * 64)
    adapter.start()
    assert adapter.status() == "up"
    adapter.stop()
    assert adapter.status() == "down"


def test_matlab_adapter_is_a_stub_for_the_project_lead():
    adapter = MatlabAdapter()
    assert adapter.status() == "down"
    with pytest.raises(NotImplementedError):
        adapter.analyze_image("a" * 64)
    with pytest.raises(NotImplementedError):
        adapter.run_simulation({})


def test_factory_returns_the_fake_adapter_in_fake_mode(monkeypatch):
    monkeypatch.setattr(settings, "matlab_fake", True)
    engine_adapter.reset_adapter()
    try:
        adapter = engine_adapter.get_adapter()
        assert isinstance(adapter, FakeAdapter)
        assert adapter.status() == "up"
        assert engine_adapter.get_adapter() is adapter  # one adapter per process
    finally:
        engine_adapter.reset_adapter()


def test_fake_simulation_is_labelled_demo():
    result = started().run_simulation({"anything": 1})
    assert result["engine_mode"] == "demo_stub"


def test_artifact_inside_output_folder_is_accepted(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "heatmap.png").write_bytes(b"x")
    assert resolve_artifact_path("heatmap.png", out) == (out / "heatmap.png").resolve()


def test_artifact_outside_output_folder_is_rejected(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    other = tmp_path / "other.png"
    other.write_bytes(b"x")
    with pytest.raises(ValueError):
        resolve_artifact_path(str(other), out)


def test_artifact_path_traversal_is_rejected(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (tmp_path / "secret.txt").write_bytes(b"x")
    with pytest.raises(ValueError):
        resolve_artifact_path("../secret.txt", out)


def test_missing_artifact_is_rejected(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError):
        resolve_artifact_path("nope.png", out)


def test_engine_crash_flags_the_case_and_stores_no_prediction(client, make_user, monkeypatch):
    class Broken:
        def analyze_image(self, sha):
            raise RuntimeError("engine crashed")

    monkeypatch.setattr(engine_adapter, "get_adapter", lambda: Broken())
    make_user(email="doc@example.com", role="clinician", must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": "doc@example.com", "password": PASSWORD}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    img = PILImage.frombytes("RGB", (300, 300), os.urandom(300 * 300 * 3))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    response = client.post(
        "/api/cases", headers=headers, files={"file": ("a.png", buf.getvalue(), "image/png")}
    )
    assert response.status_code == 202

    detail = client.get(f"/api/cases/{response.json()['id']}", headers=headers).json()
    assert "analysis_error" in detail["flags"]
    assert detail["status"] == "uploaded"
    assert detail["prediction"] is None
    assert detail["quality"] is None