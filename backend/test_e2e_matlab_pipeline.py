"""End-to-end integration test of the live MATLAB R2026b + AI/ML pipeline.

Tests:
1. Live MATLAB Engine initialization and model loading
2. Operator upload of authentic fundus image
3. Real MATLAB image quality assessment (usable)
4. Real EfficientNet-B0 inference (grade, 5 class scores, confidence)
5. Real Grad-CAM heatmap generation and storage in storage/heatmaps/
6. Authenticated retrieval of real heatmap via GET /api/images/{id}/heatmap
7. Clinician review submission and case completion
8. Negative test: Degraded image rejection -> needs_recapture (Quality-First rule)
9. Role-based access control tests on heatmap endpoint (401 unauthenticated, 403 unauthorized)
"""

import io
import os
import sys
import time
import uuid
from pathlib import Path
from PIL import Image as PILImage
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models.case import Case, Image, QualityResult, Prediction, Review
from app.services import engine_adapter
from sqlalchemy import select

def run_e2e_matlab_test():
    print("=" * 70)
    print("RETINAGUIDE XAI: PHASE 10 LIVE MATLAB END-TO-END INTEGRATION TEST")
    print("=" * 70)

    # Configure live MATLAB mode
    settings.matlab_fake = False
    engine_adapter.reset_adapter()

    client = TestClient(app)

    # Step 1: Health check before startup
    print("\n--- STEP 1: INITIAL HEALTH STATUS ---")
    h_before = client.get("/api/health").json()
    print("Health before engine start:", h_before)
    assert h_before["engine"] == "real"
    assert h_before["engine_state"] in ("starting", "down")

    # Step 2: Initialize MATLAB Adapter
    print("\n--- STEP 2: START LIVE MATLAB ENGINE ADAPTER ---")
    adapter = engine_adapter.get_adapter()
    assert adapter.status() == "up"
    print("MATLAB Engine initialized. Status:", adapter.status())

    h_after = client.get("/api/health").json()
    print("Health after engine start:", h_after)
    assert h_after["status"] == "ok"
    assert h_after["engine"] == "real"
    assert h_after["engine_state"] == "up"
    assert h_after["model_loaded"] is True

    # Step 3: Login as Operator
    print("\n--- STEP 3: AUTHENTICATE OPERATOR ---")
    op_login = client.post("/api/auth/login", json={"email": "operator@example.com", "password": "Operator1234!"})
    assert op_login.status_code == 200, f"Operator login failed: {op_login.text}"
    op_token = op_login.json()["access_token"]
    op_headers = {"Authorization": f"Bearer {op_token}"}
    print("Operator logged in successfully.")

    # Step 4: Upload Real Fundus Image
    print("\n--- STEP 4: UPLOAD REAL FUNDUS IMAGE ---")
    test_matlab_dir = Path(__file__).resolve().parents[1] / "matlab"
    legacy_dir = Path(r"C:\Users\azizn\RetinaGuideXAI\matlab")
    base_m_dir = test_matlab_dir if test_matlab_dir.exists() else legacy_dir

    fundus_path = base_m_dir / "test_images" / "fundus_test.jpeg"
    with open(fundus_path, "rb") as f:
        fundus_data = f.read() + os.urandom(8)
    patient_ref = f"MATLAB-E2E-{uuid.uuid4().hex[:6]}"

    upload_res = client.post(
        "/api/cases",
        data={"patient_ref": patient_ref, "eye": "left"},
        files={"file": ("fundus_test.jpeg", fundus_data, "image/jpeg")},
        headers=op_headers,
    )
    assert upload_res.status_code == 202, f"Upload failed: {upload_res.text}"
    case_data = upload_res.json()
    case_id = case_data["id"]
    print(f"Case created #{case_id}, status: {case_data['status']}")

    # Step 5: Wait for Background Analysis (MATLAB Quality + Inference + Grad-CAM)
    print("\n--- STEP 5: WAIT FOR MATLAB ANALYSIS COMPLETION ---")
    max_wait_s = 60
    start_t = time.time()
    graded_case = None
    while time.time() - start_t < max_wait_s:
        res = client.get(f"/api/cases/{case_id}", headers=op_headers)
        assert res.status_code == 200
        case_info = res.json()
        status = case_info["status"]
        print(f"  Polling case #{case_id}... status={status} ({round(time.time() - start_t, 1)}s)")
        if status in ("graded", "needs_recapture", "flagged"):
            graded_case = case_info
            break
        time.sleep(2)

    assert graded_case is not None, f"Analysis timed out after {max_wait_s}s"
    assert graded_case["status"] == "graded", f"Expected graded status, got {graded_case['status']}"
    print("\nLive MATLAB Analysis Completed Successfully!")

    # Step 6: Verify Real Prediction and Quality Results
    print("\n--- STEP 6: VERIFY AI OUTPUTS ---")
    quality = graded_case["quality"]
    prediction = graded_case["prediction"]
    image_id = graded_case.get("image_id") or graded_case.get("image", {}).get("id")

    print("Quality result:", quality)
    print("Prediction result:", prediction)

    assert quality["verdict"] == "usable"
    assert quality["engine_mode"] == "matlab_production"
    assert quality["reason_codes"] == []

    assert prediction["grade"] in (0, 1, 2, 3, 4)
    assert len(prediction["class_scores"]) == 5
    assert 0.0 <= prediction["model_score"] <= 1.0
    print(f"Predicted Grade: {prediction['grade']} | Confidence: {prediction['model_score']}")
    print(f"Five-Class Scores: {prediction['class_scores']}")

    # Step 7: Verify Grad-CAM Heatmap Retrieval
    print("\n--- STEP 7: VERIFY AUTHENTICATED GRAD-CAM HEATMAP ---")
    heatmap_res = client.get(f"/api/images/{image_id}/heatmap", headers=op_headers)
    assert heatmap_res.status_code == 200, f"Heatmap retrieval failed: {heatmap_res.status_code}"
    assert heatmap_res.headers["content-type"] == "image/png"
    assert heatmap_res.headers["cache-control"] == "private, no-store"

    # Verify heatmap image with PIL
    hm_img = PILImage.open(io.BytesIO(heatmap_res.content))
    print(f"Heatmap retrieved: {hm_img.size}, format: {hm_img.format}, mode: {hm_img.mode}")
    assert hm_img.size == (384, 384)
    assert hm_img.mode == "RGBA"
    print("Grad-CAM Heatmap verified: Authentic 384x384 RGBA artifact served.")

    # Step 8: Security Tests on Heatmap Endpoint
    print("\n--- STEP 8: HEATMAP ENDPOINT SECURITY TESTS ---")
    # 401 unauthenticated
    unauth = client.get(f"/api/images/{image_id}/heatmap")
    assert unauth.status_code == 401
    print("  Verified unauthenticated access returns 401")

    # 403 unauthorized role (planner)
    plan_login = client.post("/api/auth/login", json={"email": "planner@example.com", "password": "Planner1234!"})
    plan_headers = {"Authorization": f"Bearer {plan_login.json()['access_token']}"}
    forbidden = client.get(f"/api/images/{image_id}/heatmap", headers=plan_headers)
    assert forbidden.status_code == 403
    print("  Verified unauthorized role (planner) returns 403")

    # Step 9: Clinician Review
    print("\n--- STEP 9: CLINICIAN REVIEW SUBMISSION ---")
    req_res = client.post(f"/api/cases/{case_id}/request-review", headers=op_headers)
    assert req_res.status_code == 200, f"Request review failed: {req_res.text}"

    clin_login = client.post("/api/auth/login", json={"email": "clinician@example.com", "password": "Clinician1234!"})
    clin_headers = {"Authorization": f"Bearer {clin_login.json()['access_token']}"}
    review_res = client.post(
        f"/api/cases/{case_id}/review",
        json={"decision": "confirm", "final_grade": None, "notes": "Verified with MATLAB EfficientNet-B0 + Grad-CAM."},
        headers=clin_headers,
    )
    assert review_res.status_code == 201, f"Review failed: {review_res.text}"
    reviewed_case = client.get(f"/api/cases/{case_id}", headers=clin_headers).json()
    assert reviewed_case["status"] == "reviewed"
    assert reviewed_case["latest_review"]["decision"] == "confirm"
    # Step 9b: Verify Live PDF Report Download with MATLAB
    print("\n--- STEP 9b: VERIFY LIVE PDF REPORT GENERATION & DOWNLOAD ---")
    pdf_res = client.get(f"/api/cases/{case_id}/report.pdf", headers=clin_headers)
    assert pdf_res.status_code == 200, f"Live PDF generation failed: {pdf_res.status_code} - {pdf_res.text}"
    assert "application/pdf" in pdf_res.headers.get("content-type", "")
    assert pdf_res.content.startswith(b"%PDF-1.")
    print(f"Live PDF Report successfully generated! Size: {len(pdf_res.content)} bytes, header: {pdf_res.content[:8].decode('ascii', errors='ignore')}")

    # Step 10: Negative Test - Degraded Image
    print("\n--- STEP 10: NEGATIVE QUALITY TEST (DEGRADED IMAGE) ---")
    dark_path = base_m_dir / "test_images" / "quality_tests" / "dark_test.jpeg"
    with open(dark_path, "rb") as f:
        dark_data = f.read() + os.urandom(8)
    dark_patient_ref = f"MATLAB-DARK-{uuid.uuid4().hex[:6]}"

    dark_upload = client.post(
        "/api/cases",
        data={"patient_ref": dark_patient_ref, "eye": "right"},
        files={"file": ("dark_test.jpeg", dark_data, "image/jpeg")},
        headers=op_headers,
    )
    assert dark_upload.status_code == 202, f"Dark upload failed: {dark_upload.text}"
    dark_case_id = dark_upload.json()["id"]

    start_t = time.time()
    dark_case = None
    while time.time() - start_t < max_wait_s:
        res = client.get(f"/api/cases/{dark_case_id}", headers=op_headers)
        case_info = res.json()
        if case_info["status"] in ("needs_recapture", "flagged"):
            dark_case = case_info
            break
        time.sleep(2)

    assert dark_case is not None
    assert dark_case["status"] == "needs_recapture"
    assert dark_case["prediction"] is None, "Quality-First violation: Unusable image must not have prediction!"
    assert dark_case["quality"]["verdict"] == "unusable"
    assert len(dark_case["quality"]["reason_codes"]) > 0
    print("Degraded image properly rejected. Case transitioned to needs_recapture with reasons:")
    for r in dark_case["quality"]["reason_codes"]:
        print(f"  - {r}")

    # Step 11: Cleanup
    print("\n--- STEP 11: SHUTDOWN MATLAB ADAPTER ---")
    engine_adapter.reset_adapter()
    print("MATLAB Adapter shut down cleanly.")

    print("\n" + "=" * 70)
    print("ALL 11 END-TO-END INTEGRATION TEST STEPS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_e2e_matlab_test()
