from datetime import datetime

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.config import ROOT
from app.db import init_db, make_engine, session_factory
from app.models.db import Group, Message


@pytest.fixture
def engine():
    eng = make_engine("sqlite://")
    init_db(eng)
    return eng


def test_relative_sqlite_path_resolves_under_repo_root():
    eng = make_engine("sqlite:///data/x.db")
    assert eng.url.database == str(ROOT / "data" / "x.db")


def test_init_creates_tables_and_fts(engine):
    names = set(inspect(engine).get_table_names())
    assert {"groups", "users", "memberships", "messages", "chunks", "query_logs"} <= names
    with engine.connect() as c:
        c.execute(
            text("INSERT INTO chunks_fts(rowid, text_clean, group_id) VALUES (1, 'paisa kab', 1)")
        )
        hits = c.execute(text("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'paisa'")).all()
    assert hits == [(1,)]


def test_duplicate_dedup_key_rejected(engine):
    Session = session_factory(engine)
    with Session() as s:
        g = Group(wa_group_id="g1", name="G")
        s.add(g)
        s.flush()
        for _ in range(2):
            s.add(Message(group_id=g.id, ts=datetime(2026, 1, 1), text_raw="hi", dedup_key="k1"))
        with pytest.raises(IntegrityError):
            s.flush()
