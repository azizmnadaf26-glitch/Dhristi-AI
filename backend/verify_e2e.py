import os
import sys
import time
import json
import sqlite3
import httpx

BASE_URL = "http://127.0.0.1:8000"
DB_PATH = r"C:\Users\azizn\DhristiAI\backend\screening.db"

results = {
    "workflows": {},
    "security": {},
    "negative": {},
    "db": {}
}

def log_test(category, name, passed, details=""):
    results[category][name] = {"passed": passed, "details": details}
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {category} -> {name}: {details}")

client = httpx.Client(base_url=BASE_URL, timeout=30.0)

# 1. Health check
res = client.get("/api/health")
log_test("workflows", "Health Check", res.status_code == 200, res.text)

# WORKFLOW 1: OPERATOR
# Login
op_res = client.post("/api/auth/login", json={"email": "operator@example.com", "password": "Operator1234!"})
op_data = op_res.json()
op_token = op_data.get("access_token")
op_headers = {"Authorization": f"Bearer {op_token}"}
log_test("workflows", "Workflow 1 - Operator Login", op_res.status_code == 200 and "access_token" in op_data)

# Verify Profile /api/me
me_res = client.get("/api/me", headers=op_headers)
me_data = me_res.json()
log_test("workflows", "Workflow 1 - Operator Profile (/api/me)", me_res.status_code == 200 and me_data.get("role") == "operator", f"Role: {me_data.get('role')}")

# Upload Fundus Image
sample_img_path = r"C:\Users\azizn\DhristiAI\frontend\public\retinal\fundus-3.png"
with open(sample_img_path, "rb") as f:
    img_bytes = f.read()

files = {"file": ("fundus_test_3.png", img_bytes, "image/png")}
data = {"patient_ref": "TEST-PATIENT-E2E-003", "eye": "left"}
upload_res = client.post("/api/cases", headers=op_headers, files=files, data=data)
upload_json = upload_res.json()
if upload_res.status_code == 409 and "details" in upload_json.get("error", {}):
    case_id = upload_json["error"]["details"]["case_id"]
else:
    case_id = upload_json.get("id")

log_test("workflows", "Workflow 1 - Operator Image Upload", case_id is not None, f"Case ID: {case_id}")

# Negative Test: Duplicate image upload
dup_res = client.post("/api/cases", headers=op_headers, files={"file": ("fundus_dup.png", img_bytes, "image/png")})
log_test("negative", "Duplicate Image Submission Rejected (409)", dup_res.status_code == 409, f"Code: {dup_res.json().get('error', {}).get('code')}")

# Wait for processing
case_detail = None
for _ in range(10):
    time.sleep(1)
    c_res = client.get(f"/api/cases/{case_id}", headers=op_headers)
    if c_res.status_code == 200:
        case_detail = c_res.json()
        if case_detail.get("status") != "uploaded":
            break

log_test("workflows", "Workflow 1 - Case Analysis Complete", case_detail and case_detail.get("status") in ("graded", "needs_recapture", "analyzed"), f"Engine Status: {case_detail.get('status') if case_detail else 'N/A'}")

# Worklist check
cases_res = client.get("/api/cases?limit=10&page=1", headers=op_headers)
cases_data = cases_res.json()
items = cases_data.get("items", cases_data if isinstance(cases_data, list) else [])
found_case = any(str(c.get("id")) == str(case_id) for c in items)
log_test("workflows", "Workflow 1 - Case in Screening Worklist", found_case, f"Found case {case_id} in worklist")

# Authenticated image retrieval
img_id = case_detail.get("image_id") or case_id
img_file_res = client.get(f"/api/images/{img_id}/file", headers=op_headers)
log_test("workflows", "Workflow 1 - Authenticated Image Retrieval", img_file_res.status_code == 200 and len(img_file_res.content) > 0, f"Size: {len(img_file_res.content)} bytes, Content-Type: {img_file_res.headers.get('content-type')}")

# WORKFLOW 2: IMAGE VALIDATION
# Invalid file type (.txt)
invalid_file = {"file": ("malicious.txt", b"plain text that is definitely not a png or jpeg image", "text/plain")}
inv_res = client.post("/api/cases", headers=op_headers, files=invalid_file)
log_test("workflows", "Workflow 2 - Reject Invalid File Type", inv_res.status_code in (400, 415, 422), f"Status: {inv_res.status_code}")

# Empty file
empty_file = {"file": ("empty.jpg", b"", "image/jpeg")}
empty_res = client.post("/api/cases", headers=op_headers, files=empty_file)
log_test("workflows", "Workflow 2 - Reject Empty File", empty_res.status_code in (400, 422), f"Status: {empty_res.status_code}")

# Invalid eye value
bad_eye_data = {"eye": "middle"}
bad_eye_files = {"file": ("fundus_test.png", img_bytes, "image/png")}
bad_eye_res = client.post("/api/cases", headers=op_headers, files=bad_eye_files, data=bad_eye_data)
log_test("workflows", "Workflow 2 - Reject Invalid Eye Parameter", bad_eye_res.status_code == 422, f"Status: {bad_eye_res.status_code}")

# WORKFLOW 3: CLINICIAN
# Clinician Login
cl_res = client.post("/api/auth/login", json={"email": "clinician@example.com", "password": "Clinician1234!"})
cl_token = cl_res.json().get("access_token")
cl_headers = {"Authorization": f"Bearer {cl_token}"}
log_test("workflows", "Workflow 3 - Clinician Login", cl_res.status_code == 200 and "access_token" in cl_res.json())

# Clinician access case
cl_case_res = client.get(f"/api/cases/{case_id}", headers=cl_headers)
log_test("workflows", "Workflow 3 - Clinician Case Access", cl_case_res.status_code == 200)

# Request review first
req_review_res = client.post(f"/api/cases/{case_id}/request-review", headers=cl_headers)
log_test("workflows", "Workflow 3 - Clinician Request Review", req_review_res.status_code in (200, 204), f"Status: {req_review_res.status_code}")

# Clinician Submit Review
review_payload = {
    "decision": "confirm",
    "final_grade": None,
    "notes": "End-to-End integration test confirmed Dr. assessment."
}
review_res = client.post(f"/api/cases/{case_id}/review", headers=cl_headers, json=review_payload)
log_test("workflows", "Workflow 3 - Clinician Review Submission", review_res.status_code in (200, 201), f"Status: {review_res.status_code}")

# Verify case status updated
updated_case_res = client.get(f"/api/cases/{case_id}", headers=cl_headers)
updated_case = updated_case_res.json()
log_test("workflows", "Workflow 3 - Case Review Status Updated", updated_case.get("status") in ("reviewed", "completed") or updated_case.get("latest_review") is not None, f"Status: {updated_case.get('status')}")

# WORKFLOW 4: PLANNER
pl_res = client.post("/api/auth/login", json={"email": "planner@example.com", "password": "Planner1234!"})
pl_token = pl_res.json().get("access_token")
pl_headers = {"Authorization": f"Bearer {pl_token}"}
log_test("workflows", "Workflow 4 - Planner Login", pl_res.status_code == 200 and "access_token" in pl_res.json())

# Operational Summary
summary_res = client.get("/api/summary", headers=pl_headers)
log_test("workflows", "Workflow 4 - Operational Summary", summary_res.status_code == 200 and "total_cases" in summary_res.json(), f"Total cases: {summary_res.json().get('total_cases')}")

# Evaluation Data
eval_res = client.get("/api/evaluation/latest", headers=pl_headers)
log_test("workflows", "Workflow 4 - Evaluation Dashboard", eval_res.status_code in (200, 404), f"Status: {eval_res.status_code}")

# Run Simulation
sim_payload = {
    "weekly_screenings": 350,
    "devices": 5,
    "weeks": 12
}
sim_res = client.post("/api/simulations", headers=pl_headers, json=sim_payload)
sim_data = sim_res.json()
sim_id = sim_data.get("id")
log_test("workflows", "Workflow 4 - Launch Simulation", sim_res.status_code in (200, 201, 202) and sim_id is not None, f"Sim ID: {sim_id}, Status: {sim_data.get('status')}")

# Poll Simulation Completion
for _ in range(5):
    time.sleep(1)
    s_res = client.get(f"/api/simulations/{sim_id}", headers=pl_headers)
    if s_res.status_code == 200 and s_res.json().get("status") in ("completed", "failed"):
        sim_data = s_res.json()
        break

log_test("workflows", "Workflow 4 - Simulation Run Completed", sim_data.get("status") == "completed", f"Status: {sim_data.get('status')}")

# Retrieve Simulation History
sim_list_res = client.get("/api/simulations", headers=pl_headers)
log_test("workflows", "Workflow 4 - Retrieve Simulation History", sim_list_res.status_code == 200 and len(sim_list_res.json().get("items", [])) > 0, f"Simulations count: {sim_list_res.json().get('total')}")

# WORKFLOW 5: ADMIN
ad_res = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "AdminPass1234!"})
ad_token = ad_res.json().get("access_token")
ad_headers = {"Authorization": f"Bearer {ad_token}"}
log_test("workflows", "Workflow 5 - Admin Login", ad_res.status_code == 200 and "access_token" in ad_res.json())

# Get User List
users_res = client.get("/api/admin/users", headers=ad_headers)
log_test("workflows", "Workflow 5 - User Management List", users_res.status_code == 200 and users_res.json().get("total", 0) >= 4, f"Total users: {users_res.json().get('total')}")

# Create Test User
test_email = f"e2e_user_{int(time.time())}@example.com"
create_res = client.post("/api/admin/users", headers=ad_headers, json={"email": test_email, "role": "operator"})
new_user_data = create_res.json()
test_user_id = new_user_data.get("user", {}).get("id")
log_test("workflows", "Workflow 5 - Admin Create User", create_res.status_code == 201 and test_user_id is not None, f"Created ID: {test_user_id}")

# Update User Status
if test_user_id:
    patch_res = client.patch(f"/api/admin/users/{test_user_id}", headers=ad_headers, json={"is_active": False})
    log_test("workflows", "Workflow 5 - Admin Deactivate User", patch_res.status_code == 200 and patch_res.json().get("is_active") is False)

    # Password Reset
    reset_res = client.post(f"/api/admin/users/{test_user_id}/reset-password", headers=ad_headers)
    log_test("workflows", "Workflow 5 - Admin Password Reset", reset_res.status_code == 200 and "temp_password" in reset_res.json())

# Admin Audit Log
audit_res = client.get("/api/admin/audit", headers=ad_headers)
log_test("workflows", "Workflow 5 - Admin Audit Log", audit_res.status_code == 200 and audit_res.json().get("total", 0) > 0, f"Total audit events: {audit_res.json().get('total')}")

# Model Registry
models_res = client.get("/api/admin/models", headers=ad_headers)
log_test("workflows", "Workflow 5 - Model Registry", models_res.status_code == 200, f"Models total: {models_res.json().get('total')}")

# WORKFLOW 6: SESSION & SECURITY
# Refresh token test (with cookies)
refresh_res = client.post("/api/auth/refresh", cookies=op_res.cookies)
log_test("security", "Session Refresh with Cookie", refresh_res.status_code == 200 and "access_token" in refresh_res.json())

# Unauthorized endpoint access (No Auth)
no_auth_res = client.get("/api/admin/users")
log_test("security", "Reject Unauthenticated Admin Access", no_auth_res.status_code in (401, 403))

# RBAC violation: Operator accessing Admin API
op_forbidden = client.get("/api/admin/users", headers=op_headers)
log_test("security", "RBAC - Operator Forbidden on Admin API", op_forbidden.status_code in (401, 403))

# RBAC violation: Clinician accessing Admin Audit
cl_forbidden = client.get("/api/admin/audit", headers=cl_headers)
log_test("security", "RBAC - Clinician Forbidden on Admin Audit", cl_forbidden.status_code in (401, 403))

# Invalid Token test
bad_auth = client.get("/api/me", headers={"Authorization": "Bearer invalid_garbage_token"})
log_test("security", "Reject Malformed/Invalid Token", bad_auth.status_code in (401, 403))

# DATABASE VERIFICATION
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("SELECT count(*) FROM users")
user_count = cursor.fetchone()[0]
log_test("db", "Database Users Table Count", user_count >= 4, f"Found {user_count} users")

cursor.execute("SELECT count(*) FROM cases")
case_count = cursor.fetchone()[0]
log_test("db", "Database Cases Table Count", case_count > 0, f"Found {case_count} cases")

cursor.execute("SELECT count(*) FROM audit_log")
audit_count = cursor.fetchone()[0]
log_test("db", "Database Audit Events Count", audit_count > 0, f"Found {audit_count} audit events in audit_log")

cursor.execute("SELECT count(*) FROM reviews")
review_count = cursor.fetchone()[0]
log_test("db", "Database Reviews Count", review_count > 0, f"Found {review_count} clinical reviews")

cursor.execute("SELECT count(*) FROM predictions")
pred_count = cursor.fetchone()[0]
log_test("db", "Database Predictions Count", pred_count > 0, f"Found {pred_count} prediction records")

cursor.execute("PRAGMA foreign_key_check")
fk_errors = cursor.fetchall()
log_test("db", "Database Foreign Key Integrity", len(fk_errors) == 0, f"FK errors: {len(fk_errors)}")

conn.close()

# Save output
with open(r"C:\Users\azizn\DhristiAI\backend\e2e_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n--- SUMMARY ---")
all_passed = True
for cat, tests in results.items():
    for name, data in tests.items():
        if not data["passed"]:
            all_passed = False
            print(f"FAILED: {cat} -> {name}: {data['details']}")

if all_passed:
    print("ALL INTEGRATION, WORKFLOW, SECURITY & DB VERIFICATIONS PASSED!")
