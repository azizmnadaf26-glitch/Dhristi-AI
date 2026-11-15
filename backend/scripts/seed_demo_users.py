"""Seed standard demo/testing accounts safely.

Creates admin, clinician, and operator accounts if they do not exist.
"""
from sqlalchemy import select

from app.db import SessionLocal
from app.models.user import User
from app.security.hashing import hash_password

DEFAULT_USERS = [
    ("admin@example.com", "AdminPass1234!", "admin"),
    ("clinician@example.com", "Clinician1234!", "clinician"),
    ("operator@example.com", "Operator1234!", "operator"),
]


def seed_users() -> None:
    created = 0
    with SessionLocal() as db:
        for email, password, role in DEFAULT_USERS:
            existing = db.scalar(select(User).where(User.email == email))
            if existing is None:
                db.add(
                    User(
                        email=email,
                        password_hash=hash_password(password),
                        role=role,
                        must_change_password=False,
                    )
                )
                print(f"[+] Created {role}: {email}")
                created += 1
            else:
                print(f"[-] {role} already exists: {email}")
        if created > 0:
            db.commit()
            print(f"Successfully seeded {created} demo user(s).")
        else:
            print("All demo users already exist. No action needed.")


if __name__ == "__main__":
    seed_users()
