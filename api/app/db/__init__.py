"""Engine, sessions, and schema setup. The relational DB is the source of truth (TRD §6)."""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import ROOT, get_settings
from app.models.db import Base

# Plain (not contentless) FTS5 table so rows can be deleted by rowid on reindex.
# rowid = chunks.id.
FTS_DDL = "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text_clean, group_id UNINDEXED)"


def make_engine(url: str) -> Engine:
    u = make_url(url)
    if u.drivername.startswith("sqlite") and u.database and not Path(u.database).is_absolute():
        path = ROOT / u.database
        path.parent.mkdir(parents=True, exist_ok=True)
        u = u.set(database=str(path))
    engine = create_engine(u)
    if u.drivername.startswith("sqlite"):
        event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    return engine


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(FTS_DDL))


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _Session
    if _engine is None:
        _engine = make_engine(get_settings().db_url)
        init_db(_engine)
        _Session = session_factory(_engine)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """FastAPI dependency. Chains open their own short sessions (e.g. the FTS5 retriever)."""
    get_engine()
    return _Session
