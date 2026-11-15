"""Test PDF report download endpoint with authentication, authorization, and PDF header verification."""

import io
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.case import Case, Image, Prediction, QualityResult
from app.models.user import User
from app.security.hashing import hash_password

def run_pdf_endpoint_test():
    print("======================================================================")
    print("VERIFYING PDF REPORT DOWNLOAD ENDPOINT")
    print("======================================================================")

    client = TestClient(app)

    with SessionLocal() as db:
        # Create test operator and clinician
        op = db.query(User).filter(User.email == "test_pdf_op@example.com").first()
        if not op:
            op = User(
                email="test_pdf_op@example.com",
                password_hash=hash_password("OperatorPass1234!"),
                role="operator",
                must_change_password=False,
            )
            db.add(op)
            db.commit()
            db.refresh(op)

        other_op = db.query(User).filter(User.email == "other_op@example.com").first()
        if not other_op:
            other_op = User(
                email="other_op@example.com",
                password_hash=hash_password("OtherPass1234!"),
                role="operator",
                must_change_password=False,
            )
            db.add(other_op)
            db.commit()
            db.refresh(other_op)

        # Create test case for operator op
        case = Case(
            created_by=op.id,
            patient_ref="TEST-PATIENT-PDF",
            eye="left",
            status="graded",
            flags=[],
        )
        db.add(case)
        db.commit()
        db.refresh(case)

        # Add image
        img = Image(
            case_id=case.id,
            filename="test_fundus.jpeg",
            sha256="0859e4204a7744da",
            size_bytes=78075,
        )
        db.add(img)
        db.commit()
        db.refresh(img)

        # Add quality
        q = QualityResult(
            case_id=case.id,
            image_id=img.id,
            verdict="usable",
            reason_codes=[],
            engine_mode="matlab_production",
        )
        db.add(q)

        # Add prediction
        p = Prediction(
            case_id=case.id,
            image_id=img.id,
            grade=0,
            class_scores=[0.978264, 0.00638, 0.004772, 0.007909, 0.002675],
            model_score=0.978264,
            referable=False,
            low_confidence=False,
        )
        db.add(p)
        db.commit()

        case_id = case.id

    # 1. Login as operator
    login_res = client.post(
        "/api/auth/login",
        json={"email": "test_pdf_op@example.com", "password": "OperatorPass1234!"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Step 1: Operator authenticated successfully.")

    # 2. Download PDF report
    pdf_res = client.get(f"/api/cases/{case_id}/report.pdf", headers=headers)
    assert pdf_res.status_code == 200, f"PDF download failed: {pdf_res.status_code} - {pdf_res.text}"
    assert "application/pdf" in pdf_res.headers.get("content-type", ""), f"Wrong content-type: {pdf_res.headers}"
    assert pdf_res.content.startswith(b"%PDF-"), f"Not a valid PDF header: {pdf_res.content[:20]}"
    print(f"Step 2: PDF report downloaded successfully! ({len(pdf_res.content)} bytes, header: {pdf_res.content[:8].decode('ascii', errors='ignore')})")

    # 3. Test alternate /pdf route
    pdf_res2 = client.get(f"/api/cases/{case_id}/pdf", headers=headers)
    assert pdf_res2.status_code == 200
    assert pdf_res2.content.startswith(b"%PDF-")
    print("Step 3: Alternate /pdf endpoint also verified successfully.")

    # 4. Security: Unauthenticated request must return 401
    unauth_res = client.get(f"/api/cases/{case_id}/report.pdf")
    assert unauth_res.status_code == 401
    print("Step 4: Unauthenticated request blocked with 401.")

    # 5. Security: Planner role must return 403
    plan_login = client.post(
        "/api/auth/login",
        json={"email": "planner@example.com", "password": "Planner1234!"},
    )
    if plan_login.status_code == 200:
        plan_headers = {"Authorization": f"Bearer {plan_login.json()['access_token']}"}
        plan_res = client.get(f"/api/cases/{case_id}/report.pdf", headers=plan_headers)
        assert plan_res.status_code == 403
        print("Step 5: Unauthorized planner role blocked with 403.")

    # 6. Security: Cross-operator access must return 404
    other_login = client.post(
        "/api/auth/login",
        json={"email": "other_op@example.com", "password": "OtherPass1234!"},
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    cross_res = client.get(f"/api/cases/{case_id}/report.pdf", headers=other_headers)
    assert cross_res.status_code == 404
    print("Step 6: Cross-operator scoping enforced; access to other operator's report returned 404.")

    print("\nALL PDF ENDPOINT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_pdf_endpoint_test()
