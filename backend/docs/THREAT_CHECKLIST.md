# RetinaGuide XAI Backend: Threat Checklist

Decision support only. Not a diagnosis.

This lists each threat, the control in the code, and the test that proves it. "(verify)" means the test was matched by file name and should be confirmed by reading the test. "No test" means no automated proof exists. All engine results are demo/stub data.

## A. Authentication and sessions

| # | Threat | Control | Proving test |
|---|---|---|---|
| A1 | Password guessing | Lockout after 5 failed logins for 15 minutes (423) | test_auth_login.py, test_security_auth.py |
| A2 | Login flooding | Login rate limit per client IP (10 per minute, 429 with Retry-After) | test_rate_limit.py |
| A3 | Finding which emails exist | Same 401 for unknown email and wrong password | test_auth_login.py, test_security_auth.py |
| A4 | Stolen database leaks passwords | Passwords stored with argon2 | test_hashing.py |
| A5 | Forged or expired access token | HS256 JWT, 15-minute expiry, user reloaded from the database on every request | test_security_auth.py, test_auth_me.py |
| A6 | Stolen refresh token replayed | Rotating hashed refresh tokens, reuse of a replaced token revokes all, HttpOnly SameSite=Strict cookie | test_refresh.py, test_security_auth.py |
| A7 | Weak or default password kept | Minimum length 10, must_change_password gate | test_auth_login.py, test_auth_me.py (verify) |

## B. Authorization

| # | Threat | Control | Proving test |
|---|---|---|---|
| B1 | Unauthenticated access | Every endpoint needs a token except health, login and refresh | test_permission_walk.py |
| B2 | Wrong role reaches an endpoint | Role checks on every route, 403 and a permission_denied audit row | test_permission_walk.py, test_audit_permissions.py |
| B3 | Reading another user's case | Hidden cases return 404, operators see only their own | test_cases.py, test_images.py (verify) |
| B4 | New router forgotten in the permission test | Walk test cross-checks the OpenAPI paths against the ROUTERS list | test_permission_walk.py |
| B5 | Non-admin manages users | Admin-only user endpoints | test_admin_users.py |

## C. Uploads and files

| # | Threat | Control | Proving test |
|---|---|---|---|
| C1 | Non-image or corrupt file | Pillow validation of every upload | test_security_uploads.py, test_cases.py |
| C2 | Oversized request | Body-size check before authentication (413) | test_body_limit.py |
| C3 | Image bomb or tiny image | Max pixel and minimum side limits | test_security_uploads.py (verify) |
| C4 | Hidden metadata in images | Re-encoding strips metadata | test_security_uploads.py (verify) |
| C5 | Path traversal when serving files | UUID file names, private image endpoint, path checks | test_images.py, test_security_uploads.py |
| C6 | Engine returns a path outside its job folder | resolve_artifact_path rejects it | test_engine_adapter.py |
| C7 | Same image uploaded twice | SHA-256 per-user duplicate returns 409 | test_cases.py |

## D. Audit and privacy

| # | Threat | Control | Proving test |
|---|---|---|---|
| D1 | Audit rows edited or deleted | Append-only database triggers on audit_log and reviews | test_migrations.py, test_audit.py (verify) |
| D2 | Secrets or patient data in the audit log | Whitelisted detail keys only, never passwords, tokens, notes or bodies | test_audit.py |
| D3 | Missing audit for key actions | Login, cases, permissions and admin actions all audited | test_audit_auth.py, test_audit_cases.py, test_admin_audit.py |
| D4 | Internals leaked in error messages | One error shape with code, message and request id | test_errors.py |

## E. Availability and jobs

| # | Threat | Control | Proving test |
|---|---|---|---|
| E1 | Flooding uploads or requests | Upload and default rate limits (429) | test_rate_limit.py |
| E2 | Queue overload | Capacity check before creating a case (503 server_busy) | test_job_queue.py |
| E3 | Engine hangs | Job timeout, flag analysis_timeout, never retried | test_job_queue.py, test_engine_adapter.py (verify) |
| E4 | Jobs stuck after a crash | Sweeper flags stale cases and fails stale simulations | test_job_sweeper.py, test_job_sweeper_simulations.py |
| E5 | Two simulations at once | 409 simulation_busy | test_simulations.py |

## F. Configuration and deployment

| # | Threat | Control | Proving test |
|---|---|---|---|
| F1 | Unsafe settings (short JWT secret, wildcard CORS, bad grade, unsafe production) | validate_settings refuses to start | test_startup_checks.py, test_security_uploads.py (verify) |
| F2 | Database not migrated | Startup refuses if revision differs from the head | test_startup_checks.py, test_migrations.py |
| F3 | Foreign keys or WAL off | Startup requires them | test_startup_checks.py, test_db.py |
| F4 | Secrets committed | .env.example placeholders only | No test (manual check) |

## G. Product integrity

| # | Threat | Control | Proving test |
|---|---|---|---|
| G1 | A bad result stored for an unusable image | validate_result rejects it, case gets analysis_error | test_cases.py, test_engine_adapter.py (verify) |
| G2 | The word "probability" in the API | Contract test reads the OpenAPI text | test_contract.py |
| G3 | API changes without a regenerated contract | Contract test compares the exported file | test_contract.py |
| G4 | Simulated numbers mistaken for measured ones | Fixed label on every simulation result | test_simulation_schema.py, test_simulations.py (verify) |
| G5 | Unknown request fields accepted | Strict schemas return 422 | test_simulation_schema.py, test_cases.py (verify) |
| G6 | Evaluation targets stored as pass or fail | Backend never computes metrics, targets shown as settings | test_evaluation_api.py, test_evaluation_import.py (verify) |

## H. Known gaps (no control, or no test)

- Login rate limit is per client IP. Behind a reverse proxy it needs forwarded-IP handling.
- Chunked bodies without Content-Length are only stopped by the read limit in the upload route.
- A timed-out engine call is abandoned, not killed.
- No HTTPS inside the app. It must sit behind a TLS proxy for real use.
- No JSON log files, no backup, restore or purge scripts.
- No dependency vulnerability scan.
- Old git history contains exposed secrets and personal data. Scrub it before any push or share.