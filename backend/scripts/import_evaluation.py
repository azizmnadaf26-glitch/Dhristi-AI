"""Usage: python -m scripts.import_evaluation path\\to\\results.json"""
import json
import sys

from app.db import SessionLocal
from app.services.evaluation_import import ImportValidationError, import_evaluation


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.import_evaluation <file.json>")
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read file: {exc}")
        return 2
    db = SessionLocal()
    try:
        print(import_evaluation(db, data))
        return 0
    except ImportValidationError as exc:
        print(f"Rejected: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())