"""Write the live OpenAPI schema to docs/contract/openapi.json.

Run:  python -m scripts.export_openapi
Re-run it after every endpoint change; a test fails if the file is out of date.
"""
import json
from pathlib import Path

from app.main import app

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "contract" / "openapi.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()