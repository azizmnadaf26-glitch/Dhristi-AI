"""Verify local environment setup and configuration."""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

def run_checks() -> bool:
    print("=" * 60)
    print(" Dhristi-AI System Verification")
    print("=" * 60)

    # 1. Config validation
    try:
        from app.config import settings, validate_settings
        validate_settings()
        print("[PASS] Settings validated successfully")
        print(f"       - APP_ENV: {settings.app_env}")
        print(f"       - MATLAB_FAKE: {settings.matlab_fake}")
        print(f"       - DATABASE_URL: {settings.database_url}")
    except Exception as e:
        print(f"[FAIL] Settings error: {e}")
        return False

    # 2. Database & Migrations
    try:
        from app.db import engine
        from app.startup_checks import check_migrations, check_sqlite_pragmas
        check_migrations(engine)
        check_sqlite_pragmas(engine)
        print("[PASS] Database tables and migrations verified")
    except Exception as e:
        print(f"[FAIL] Database check failed: {e}")
        return False

    # 3. User Accounts
    try:
        from app.db import SessionLocal
        from app.models.user import User
        from sqlalchemy import select
        with SessionLocal() as db:
            users = db.scalars(select(User)).all()
            print(f"[PASS] User accounts found in DB: {len(users)}")
            for u in users:
                print(f"       - {u.role.upper()}: {u.email} (active: {u.is_active})")
            if len(users) == 0:
                print("[WARN] No users found. Run: python -m scripts.seed_demo_users")
    except Exception as e:
        print(f"[FAIL] Could not query users: {e}")
        return False

    # 4. Engine Adapter
    try:
        from app.services.engine_adapter import get_adapter
        adapter = get_adapter()
        print(f"[PASS] Engine adapter initialized (mode: {'demo/fake' if settings.matlab_fake else 'live MATLAB'})")
        print(f"       - Engine status: {adapter.status()}")
    except Exception as e:
        print(f"[FAIL] Engine initialization failed: {e}")
        return False

    print("=" * 60)
    print(" ALL BACKEND CHECKS PASSED SUCCESSFULLY!")
    print(" You can start the server with:")
    print(" uvicorn app.main:app --host 127.0.0.1 --port 8000")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)
