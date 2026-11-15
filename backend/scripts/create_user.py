"""Create a user from the command line (development helper).

Example:
    python -m scripts.create_user doc@example.com "Some-Long-Password-1" clinician --no-force-change
"""
import argparse

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models.user import User
from app.security.hashing import hash_password

ROLES = ("operator", "clinician", "planner", "admin")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument("role", choices=ROLES)
    parser.add_argument(
        "--no-force-change",
        action="store_true",
        help="Skip the forced password change (demo accounts only)",
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    if len(args.password) < settings.password_min_length:
        raise SystemExit(f"Password must be at least {settings.password_min_length} characters.")

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)) is not None:
            raise SystemExit("A user with that email already exists.")
        db.add(
            User(
                email=email,
                password_hash=hash_password(args.password),
                role=args.role,
                must_change_password=not args.no_force_change,
            )
        )
        db.commit()
    print(f"Created {args.role}: {email}")


if __name__ == "__main__":
    main()