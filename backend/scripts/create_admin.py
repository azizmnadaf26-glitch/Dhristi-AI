from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models.user import User
from app.security.hashing import hash_password


def main() -> None:
    email = settings.initial_admin_email.strip().lower()
    password = settings.initial_admin_password

    if not email or not password:
        raise SystemExit("Set INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD in .env first.")
    if len(password) < settings.password_min_length:
        raise SystemExit(
            f"INITIAL_ADMIN_PASSWORD must be at least {settings.password_min_length} characters."
        )

    with SessionLocal() as db:
        existing_admin = db.scalar(select(User).where(User.role == "admin"))
        if existing_admin is not None:
            print("An admin already exists. Nothing to do.")
            return

        db.add(
            User(
                email=email,
                password_hash=hash_password(password),
                role="admin",
                must_change_password=True,
            )
        )
        db.commit()

    # Never print the password.
    print(f"Admin created: {email} (must change password on first login)")


if __name__ == "__main__":
    main()