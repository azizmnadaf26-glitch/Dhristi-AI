import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
TRIGGERS = {
    "audit_log_no_update",
    "audit_log_no_delete",
    "reviews_no_update",
    "reviews_no_delete",
}


@pytest.fixture()
def temp_db(tmp_path):
    """A throw-away database file. The real screening.db is never touched."""
    return tmp_path / "migration_test.db"


def alembic(temp_db, *args):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{temp_db.as_posix()}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout + result.stderr


def names(temp_db, kind):
    conn = sqlite3.connect(temp_db)
    try:
        rows = conn.execute(
            "select name from sqlite_master where type = ? and name not like 'sqlite_%'",
            (kind,),
        ).fetchall()
    finally:
        conn.close()
    return {r[0] for r in rows}


def test_there_is_exactly_one_head(temp_db):
    output = alembic(temp_db, "heads")
    assert output.count("(head)") == 1


def test_upgrade_creates_tables_and_triggers(temp_db):
    alembic(temp_db, "upgrade", "head")
    tables = names(temp_db, "table")
    for expected in ("users", "refresh_tokens", "cases", "images", "quality_results",
                     "predictions", "reviews", "audit_log"):
        assert expected in tables
    assert TRIGGERS <= names(temp_db, "trigger")


def test_audit_log_is_append_only(temp_db):
    alembic(temp_db, "upgrade", "head")
    conn = sqlite3.connect(temp_db)
    try:
        conn.execute(
            "insert into audit_log (created_at, action, outcome) "
            "values ('2026-01-01 00:00:00', 'login', 'success')"
        )
        conn.commit()
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("update audit_log set action = 'changed'")
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("delete from audit_log")
        assert conn.execute("select count(*) from audit_log").fetchone()[0] == 1
    finally:
        conn.close()


def test_downgrade_to_base_and_upgrade_again(temp_db):
    alembic(temp_db, "upgrade", "head")
    alembic(temp_db, "downgrade", "base")
    assert names(temp_db, "table") <= {"alembic_version"}
    assert names(temp_db, "trigger") == set()
    alembic(temp_db, "upgrade", "head")
    assert TRIGGERS <= names(temp_db, "trigger")