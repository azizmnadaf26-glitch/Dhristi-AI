# RetinaGuide XAI Backend: Handoff

Decision support only. Not a diagnosis.

For the project lead (MATLAB, model, Grad-CAM, Simulink, App Designer, final integration). Last full test run: 30 Oct 2026.

> All engine results are demo/stub data. No real MATLAB parity or end-to-end integration has been done or is claimed.

## 1. Quick start

See README.md for setup. Run with ONE Uvicorn worker only:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health: http://127.0.0.1:8000/api/health. Docs: http://127.0.0.1:8000/api/docs.

## 2. Endpoints (27, exact, from docs/contract/openapi.json)

Every endpoint needs a bearer token except health, login and refresh. Allowed roles per route are defined in `app/security/permissions.py` and shown in tests/test_permission_walk.py.

| Method | Path | Purpose |
|---|---|---|
| GET | /api/health | Status (ok or degraded), engine (fake or real), engine_state |
| POST | /api/auth/login | Log in, returns access token, sets refresh cookie |
| POST | /api/auth/refresh | Rotate refresh token, new access token |
| POST | /api/auth/logout | Revoke refresh token |
| POST | /api/auth/change-password | Change own password |
| GET | /api/me | Current user |
| GET | /api/config | Grade labels (provisional), thresholds, settings the UI needs |
| GET | /api/summary | Summary counts |
| GET | /api/cases | List cases (paginated, scoped by role) |
| POST | /api/cases | Upload an image, returns 202 and queues analysis |
| GET | /api/cases/{case_id} | Case detail |
| POST | /api/cases/{case_id}/recapture | Replace an unusable image |
| POST | /api/cases/{case_id}/request-review | Ask for clinician review |
| POST | /api/cases/{case_id}/review | Submit a review |
| GET | /api/cases/{case_id}/report | Report data (JSON) |
| GET | /api/images/{image_id}/file | Private image file |
| GET | /api/evaluation/latest | Latest imported evaluation run |
| GET | /api/evaluation/runs | Evaluation run list |
| GET | /api/admin/models | Model versions |
| GET | /api/admin/audit | Audit log (paginated) |
| GET | /api/admin/users | List users |
| POST | /api/admin/users | Create user |
| PATCH | /api/admin/users/{user_id} | Update user |
| POST | /api/admin/users/{user_id}/reset-password | Reset a user's password |
| GET | /api/simulations | List simulations |
| POST | /api/simulations | Start a simulation (one queued or running at a time) |
| GET | /api/simulations/{simulation_id} | Simulation status and result |

NOT built: PATCH /api/cases/{id}, the /api/samples endpoints, model-version activation.

## 3. JSON contract rules

- Error shape everywhere: `{"error": {"code", "message", "details", "request_id"}}`.
- Result fields are `class_scores` and `model_score`. The banned word listed in the product rules must never appear in the API. tests/test_contract.py checks the OpenAPI text.
- Missing values are `null`, never 0. Grade 0 is a real result.
- Unknown request fields return 422.
- Timestamps are UTC, ISO 8601 with a trailing Z.
- Pagination: `page` (default 1), `page_size` (default 25, max 100). Responses have `items`, `total`, `page`, `page_size`.
- Hidden cases return 404, not 403.
- Every simulation result carries the label "Simulated estimate, not a measured result".
- Every result screen must show "Decision support only. Not a diagnosis."
- After any endpoint change run `python -m scripts.export_openapi` and commit docs/contract/openapi.json.

## 4. Engine adapter (for the project lead)

File: `app/services/engine_adapter.py`. Read it for the exact method signatures.

Interface: `EngineAdapter` with `start`, `status`, `analyze_image`, `run_simulation`, `stop`.
- `FakeAdapter` returns demo_stub data. It is the default (MATLAB_FAKE).
- `MatlabAdapter` is a documented stub that raises NotImplementedError. The project lead implements it.

Rules the real MatlabAdapter must follow:
1. Results must pass `validate_result` in `app/services/case_service.py`. An unusable image must NOT carry a prediction, or the result is rejected and the case gets flag `analysis_error`.
2. Use `class_scores` and `model_score`. Return `null` for anything missing, never 0.
3. Any file the engine writes (for example Grad-CAM overlays) must sit inside the job output folder. `resolve_artifact_path(path, output_dir)` rejects anything else.
4. Calls come from one worker thread. The caller applies timeouts (startup 180 s, job 120 s, simulation 600 s by default). A timed-out call is abandoned, not killed, and is never retried.
5. Raise an exception on failure. Do not return partial or fake data.
6. Never mark real results as demo, and never mark demo results as real. Health reports `engine: real` only when the real adapter is active.
7. Production refuses to start with the fake engine, so a real adapter is required before production use.
8. Do not call external services. The plan forbids cloud storage, external AI calls, email, SSO and managed databases.

## 5. Required settings

Must be set in `.env` (placeholders in `.env.example`; never commit `.env`):
- `JWT_SECRET` at least 32 characters when auth is enabled
- `REFERABLE_MIN_GRADE` between 0 and 4. Currently 2, PROVISIONAL
- `DATABASE_URL`, `CORS_ALLOWED_ORIGINS` (exact origins, no `*`)
- `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` only while seeding the first admin, then remove them

The full settings table is in README.md section 3.

## 6. Open issues and honest notes

- Field names, error codes, evaluation fields and simulation parameters come from the work plan, not the full Backend Specification Document.
- GRADE_LABELS and REFERABLE_MIN_GRADE are provisional.
- Simulation parameters are placeholders. Roles allowed to run simulations are an assumption.
- EVALUATION_TARGETS is empty. The evaluation import's split handling (plan says only "test") is not yet verified.
- Login rate limit is per client IP. Behind a proxy it needs forwarded-IP handling.
- Chunked bodies without Content-Length are only stopped by the read limit in the upload route.
- A case flagged by the sweeper while merely slow can later finish as graded and still carry the flag.
- Only one Uvicorn worker is supported.
- No HTTPS in the app (use a TLS proxy), no JSON log files, no backup, restore or purge scripts.
- Git history contains old exposed secrets and personal data. Scrub it with a mentor before any push, zip or share.

## 7. Test report

- Command: `pytest -q`
- Result: 253 passed, 1 warning, 79.29 s (30 Oct 2026)
- 35 test files in tests/. Threats mapped to tests are in docs/THREAT_CHECKLIST.md.
- Rows marked "(verify)" in the checklist were matched by file name and not yet confirmed by reading the tests.
- Not covered by automated tests: a real MATLAB engine, HTTPS, a dependency vulnerability scan.