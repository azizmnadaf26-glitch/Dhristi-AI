"""Pre-flight checks that run before the API accepts any request."""
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from app.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


class StartupCheckError(RuntimeError):
    """Raised when the app must refuse to start."""


def _latest_revision() -> str | None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def check_migrations(eng: Engine) -> None:
    latest = _latest_revision()
    with eng.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    if current != latest:
        raise StartupCheckError(
            f"Database is not at the latest migration (database: {current}, "
            f"latest: {latest}). Run: alembic upgrade head"
        )


def ensure_storage_dir(path: str) -> None:
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StartupCheckError(f"Cannot create storage folder '{path}': {exc}") from exc


def check_sqlite_pragmas(eng: Engine) -> None:
    if eng.dialect.name != "sqlite":
        return
    with eng.connect() as conn:
        foreign_keys = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
        journal_mode = str(conn.exec_driver_sql("PRAGMA journal_mode").scalar()).lower()
    if foreign_keys != 1:
        raise StartupCheckError("SQLite foreign_keys pragma is not ON")
    in_memory = eng.url.database in (None, "", ":memory:")
    if not in_memory and journal_mode != "wal":
        raise StartupCheckError(f"SQLite is not in WAL mode (found: {journal_mode})")


def run_startup_checks(eng: Engine, storage_dir: str | None = None) -> None:
    ensure_storage_dir(storage_dir or settings.storage_dir)
    check_sqlite_pragmas(eng)
    check_migrations(eng)