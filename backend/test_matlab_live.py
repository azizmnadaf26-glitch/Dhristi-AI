import os
import sys
import hashlib
from pathlib import Path
from PIL import Image as PILImage
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models.case import Case, Image
from app.services.engine_adapter import MatlabAdapter

def run_test():
    print("--- STEP 1: INITIALIZE MATLAB ADAPTER ---")
    adapter = MatlabAdapter()
    print("Initial status:", adapter.status())
    assert adapter.status() == "down"

    adapter.start()
    print("Status after start:", adapter.status())
    assert adapter.status() == "up"

    # Insert a test case and image record for test
    test_fundus_path = r"C:\Users\azizn\RetinaGuideXAI\matlab\test_images\fundus_test.jpeg"
    with open(test_fundus_path, "rb") as f:
        data = f.read()
    sha = hashlib.sha256(data).hexdigest()

    # Save to storage/originals
    orig_dir = Path(settings.storage_dir) / "originals"
    orig_dir.mkdir(parents=True, exist_ok=True)
    test_filename = f"matlab_test_{sha[:16]}.jpg"
    (orig_dir / test_filename).write_bytes(data)

    with SessionLocal() as db:
        case = Case(created_by=1, patient_ref="MATLAB-TEST-001", eye="left", status="uploaded", flags=[])
        db.add(case)
        db.flush()
        img = Image(case_id=case.id, filename=test_filename, sha256=sha, size_bytes=len(data))
        db.add(img)
        db.commit()
        case_id = case.id
        image_id = img.id

    print(f"Created test case #{case_id}, image #{image_id}, SHA: {sha[:16]}")

    print("--- STEP 2: ANALYZE VALID RETINAL IMAGE ---")
    res = adapter.analyze_image(sha)
    print("Result quality:", res["quality"])
    print("Result prediction:", res["prediction"])
    print("Result heatmap path:", res.get("heatmap_path"))

    assert res["quality"]["verdict"] == "usable"
    assert res["prediction"]["grade"] in (0, 1, 2, 3, 4)
    assert len(res["prediction"]["class_scores"]) == 5
    assert 0.0 <= res["prediction"]["model_score"] <= 1.0

    heatmap_file = Path(settings.storage_dir) / "heatmaps" / f"{image_id}.png"
    assert heatmap_file.is_file(), f"Heatmap file missing: {heatmap_file}"
    print(f"Verified heatmap file exists: {heatmap_file} ({heatmap_file.stat().st_size} bytes)")

    # Verify heatmap image is valid RGBA image
    with PILImage.open(heatmap_file) as hm:
        print(f"Heatmap size: {hm.size}, format: {hm.format}, mode: {hm.mode}")
        assert hm.size == (384, 384)

    print("--- STEP 3: ANALYZE DEGRADED IMAGE (QUALITY TEST) ---")
    dark_test_path = r"C:\Users\azizn\RetinaGuideXAI\matlab\test_images\quality_tests\dark_test.jpeg"
    with open(dark_test_path, "rb") as f:
        dark_data = f.read()
    dark_sha = hashlib.sha256(dark_data).hexdigest()
    dark_filename = f"matlab_dark_{dark_sha[:16]}.jpg"
    (orig_dir / dark_filename).write_bytes(dark_data)

    with SessionLocal() as db:
        dark_case = Case(created_by=1, patient_ref="MATLAB-DARK-001", eye="right", status="uploaded", flags=[])
        db.add(dark_case)
        db.flush()
        dark_img = Image(case_id=dark_case.id, filename=dark_filename, sha256=dark_sha, size_bytes=len(dark_data))
        db.add(dark_img)
        db.commit()

    dark_res = adapter.analyze_image(dark_sha)
    print("Degraded result quality:", dark_res["quality"])
    print("Degraded result prediction:", dark_res.get("prediction"))

    assert dark_res["quality"]["verdict"] == "unusable"
    assert dark_res["prediction"] is None
    assert len(dark_res["quality"]["reason_codes"]) > 0

    print("--- STEP 4: SHUTDOWN ADAPTER ---")
    adapter.stop()
    print("Status after stop:", adapter.status())
    assert adapter.status() == "down"

    print("\nALL MATLAB ENGINE ADAPTER TESTS PASSED!")

if __name__ == "__main__":
    run_test()
