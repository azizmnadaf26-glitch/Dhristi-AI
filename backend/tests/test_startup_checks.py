import pytest
from sqlalchemy import create_engine, event

from app import startup_checks
from app.startup_checks import StartupCheckError


def _make_engine(tmp_path, pragmas=True):
    eng = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    if pragmas:

        @event.listens_for(eng, "connect")
        def _set(dbapi_connection, _record):
            cur = dbapi_connection.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return eng


def _stamp(eng, revision):
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.exec_driver_sql("INSERT INTO alembic_version VALUES (?)", (revision,))


def test_empty_database_is_refused(tmp_path):
    with pytest.raises(StartupCheckError, match="alembic upgrade head"):
        startup_checks.check_migrations(_make_engine(tmp_path))


def test_old_revision_is_refused(tmp_path):
    eng = _make_engine(tmp_path)
    _stamp(eng, "000000000000")
    with pytest.raises(StartupCheckError):
        startup_checks.check_migrations(eng)


def test_latest_revision_is_accepted(tmp_path):
    eng = _make_engine(tmp_path)
    _stamp(eng, startup_checks._latest_revision())
    startup_checks.check_migrations(eng)


def test_storage_folder_is_created(tmp_path):
    target = tmp_path / "a" / "b"
    startup_checks.ensure_storage_dir(str(target))
    assert target.is_dir()


def test_missing_pragmas_are_refused(tmp_path):
    with pytest.raises(StartupCheckError, match="foreign_keys"):
        startup_checks.check_sqlite_pragmas(_make_engine(tmp_path, pragmas=False))


def test_correct_pragmas_are_accepted(tmp_path):
    startup_checks.check_sqlite_pragmas(_make_engine(tmp_path))


def test_run_startup_checks_passes_on_healthy_setup(tmp_path):
    eng = _make_engine(tmp_path)
    _stamp(eng, startup_checks._latest_revision())
    startup_checks.run_startup_checks(eng, storage_dir=str(tmp_path / "store"))
    assert (tmp_path / "store").is_dir()