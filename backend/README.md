# RetinaGuide XAI: Backend

Decision support only. Not a diagnosis.

Backend API for RetinaGuide XAI, a retinal screening decision-support web app (Tech Shodha, problem statement 1). Built with FastAPI, SQLAlchemy 2.0, Alembic and SQLite (WAL mode).

> **All engine results are demo/stub data.** There is no real MATLAB parity and no end-to-end integration with the MATLAB model yet. The project lead owns the real engine.

## WARNING: RUN EXACTLY ONE WORKER

**Always run Uvicorn with ONE worker.** The job queue, the background worker thread, the rate limiter, and the stuck-job sweeper all live inside a single Python process. Running `--workers 2` or more would create duplicate queues, duplicate sweepers and inconsistent rate limits. Never pass `--workers`.

## 1. Setup (Windows PowerShell)

Work from `E:\RetinaGuide\backend`.

```powershell
# 1. Create and activate the virtual environment (Python 3.11)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install pinned dependencies
pip install -r requirements.txt
pip check

# 3. Create your local .env from the template
Copy-Item .env.example .env

# 4. Generate a JWT secret straight into .env WITHOUT printing it
$secret = python -c "import secrets; print(secrets.token_urlsafe(48))"
(Get-Content .env) -replace '^JWT_SECRET=.*', "JWT_SECRET=$secret" | Set-Content .env
Remove-Variable secret

# 5. Create the database tables
alembic upgrade head
```

Never paste, print, commit or share your `.env` file.

### Seed the first admin

1. Open `.env` and set `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` (password at least 10 characters).
2. Run:

```powershell
python -m scripts.create_admin
```

3. Open `.env` again and **delete the two `INITIAL_ADMIN_` lines**. They are only needed once.

The first admin must change their password at first login.

### Create more users

```powershell
python -m scripts.create_user <email> <password> <role>
python -m scripts.create_user <email> <password> <role> --no-force-change
```

`--no-force-change` skips the "must change password" gate (useful for test accounts only).

## 2. Running the server

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Health check: http://127.0.0.1:8000/api/health
- Interactive API docs: http://127.0.0.1:8000/api/docs

Health returns `status` (`ok` or `degraded`), `engine` (`fake` or `real`) and `engine_state` (`starting`, `up` or `down`).

## 3. Configuration

Settings are read from `.env` (names are not case sensitive). Copy `.env.example` as a starting point.

| Setting | Default | Meaning |
|---|---|---|
| APP_ENV | `development` | Environment name. `production` refuses fake engine, disabled auth and insecure cookies |
| API_HOST | `127.0.0.1` | Host to bind |
| API_PORT | `8000` | Port to bind |
| DATABASE_URL | `sqlite:///./screening.db` | SQLAlchemy database URL (SQLite) |
| MATLAB_FAKE | `true` | Use the fake demo engine |
| JWT_SECRET | none, required | At least 32 characters when auth is enabled |
| AUTH_ENABLED | `true` | Turn authentication on or off (never off in production) |
| REFERABLE_MIN_GRADE | required, 0 to 4 | Minimum grade treated as referable. **PROVISIONAL (2)** pending clinician confirmation |
| MAX_UPLOAD_MB | 15 | Maximum upload size in MB |
| PASSWORD_MIN_LENGTH | 10 | Minimum password length |
| INITIAL_ADMIN_EMAIL | none | Used only by `create_admin`; remove after seeding |
| INITIAL_ADMIN_PASSWORD | none | Used only by `create_admin`; remove after seeding |
| ACCESS_TOKEN_MINUTES | 15 | Access token lifetime |
| REFRESH_TOKEN_HOURS | 8 | Refresh token lifetime |
| COOKIE_SECURE | `false` | Secure flag on the refresh cookie |
| MAX_FAILED_LOGINS | 5 | Failed logins before lockout |
| LOCKOUT_MINUTES | 15 | Lockout duration |
| STORAGE_DIR | storage | Folder for uploaded images |
| EVALUATION_TARGETS | empty | Target numbers shown as settings, never stored as pass/fail |
| MIN_IMAGE_SIDE_PX | 256 | Smallest accepted image side |
| MAX_IMAGE_PIXELS | 60000000 | Largest accepted image (pixels) |
| LOW_CONFIDENCE_THRESHOLD | 0.60 | Below this a result is marked low confidence |
| CORS_ALLOWED_ORIGINS | (see .env.example) | Comma-separated exact origins. `*` is refused |
| RATE_LIMIT_LOGIN_PER_MIN | 10 | Login attempts per minute per client IP |
| RATE_LIMIT_UPLOAD_PER_MIN | 20 | Uploads per minute per user |
| RATE_LIMIT_DEFAULT_PER_MIN | 240 | Other requests per minute per user |
| MATLAB_STARTUP_TIMEOUT_S | 180 | Engine startup timeout (seconds) |
| MATLAB_JOB_TIMEOUT_S | 120 | Per-image analysis timeout (seconds) |
| MATLAB_SIM_TIMEOUT_S | 600 | Simulation timeout (seconds) |
| MAX_WAITING_ANALYSES | 50 | Queue capacity before returning 503 `server_busy` |
| SWEEP_INTERVAL_S | 300 | How often the stuck-job sweeper runs (seconds) |

Entries marked "see .env.example" have a safe placeholder there. The server refuses to start on unsafe settings (short JWT secret, bad grade, `*` in CORS, unsafe production setup).

## 4. Tests

```powershell
pytest -q
pytest -q 2>&1 | Select-Object -Last 3
```

Rules of thumb:
- Run a single file with `pytest tests/test_health.py -q`. Trust the single-file "N passed" over any summed total.
- If a test fails, note only the failing test NAMES and the last error line. Do not share pytest tracebacks, because settings objects inside them can leak secrets.

After ANY endpoint change, regenerate the API contract before committing:

```powershell
python -m scripts.export_openapi
```

Otherwise `tests/test_contract.py` fails.

When adding a new router: register it in `app/main.py`, and add it to the import line and the `ROUTERS` list in `tests/test_permission_walk.py`.

## 5. Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| App refuses to start, mentions revision | Database not at the latest migration | Run `alembic upgrade head` |
| App refuses to start, mentions JWT_SECRET | Secret missing or under 32 characters | Regenerate it (setup step 4) |
| App refuses to start, mentions CORS | `*` or a bad origin list | Use exact comma-separated origins |
| 404 on a new route | Router not registered | Check `app/main.py` |
| 401 on every call | Missing or expired token | Log in again |
| 403 | Role not allowed | Use a user with the right role |
| 404 on a case you know exists | Case belongs to another operator (hidden cases return 404) | Log in as the owner or a reviewer |
| 413 on upload | File too large | Keep under MAX_UPLOAD_MB |
| 423 on login | Account locked | Wait LOCKOUT_MINUTES |
| 429 | Rate limit hit | Wait for the Retry-After seconds |
| 503 server_busy | Analysis queue full | Retry after the Retry-After seconds |
| IndentationError | Leading spaces from copying | Remove the extra spaces, save, retry |
| File empty or missing | Forgot Ctrl+S or pasted into an Untitled tab | Check the tab title, save |
| Git terminal stuck | Pager opened | Press `q`; run `git config --global core.pager cat` |

## 6. Known limitations and honest notes

- All engine results are demo/stub data. No real MATLAB parity and no end-to-end integration is claimed.
- Field names, error codes, evaluation fields and simulation parameters come from the team work plan, not from the full Backend Specification Document, which the backend teammate does not have yet.
- `GRADE_LABELS` in `/api/config` are provisional.
- `REFERABLE_MIN_GRADE=2` is provisional pending clinician confirmation.
- The login rate limit is per client IP. Behind a reverse proxy it would need forwarded-IP handling.
- The body-size limit checks Content-Length before authentication. Chunked bodies without Content-Length are only stopped by the read limit inside the upload route.
- A timed-out engine call is abandoned, not killed (Python cannot kill a thread).
- A case flagged by the sweeper while its job is merely slow can later finish as graded but still carry the flag.
- Only one Uvicorn worker is supported.
- `EVALUATION_TARGETS` is empty by default.
- Simulation parameters are placeholders. The roles allowed to run simulations are an assumption (planners and admins run, clinicians read).
- The model-version activation action (`model_version_changed` audit) is not built.
- The result validator lives in `app/services/case_service.py`, not in `docs/contract/validate_result.py`.
- NOT built (unless added later): `PATCH /api/cases/{id}`, the `/api/samples` endpoints, rotating JSON log files, and the backup, restore and purge scripts.
- The evaluation import's handling of splits (plan says only "test") still needs to be verified.

## 7. Product rules

- The product never claims to diagnose. Notice: "Decision support only. Not a diagnosis."
- API fields are `class_scores` and `model_score`.
- Missing values are `null`, never 0 (grade 0 is a real result).
- Unknown request fields return 422.
- Timestamps are UTC, ISO 8601 with Z.
- Simulation results carry the label "Simulated estimate, not a measured result".
