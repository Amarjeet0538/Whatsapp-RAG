from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.config import get_settings
from app.db import get_session_factory
from app.deps import Models, get_models
from app.indexing.vector_store import _client, _path

router = APIRouter()


@router.get("/health")
def health(Session=Depends(get_session_factory), models: Models = Depends(get_models)):
    checks = {}
    try:
        with Session() as s:
            s.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:  # report, don't crash the health check
        checks["db"] = f"error: {type(e).__name__}"
    try:
        _client(_path(models.chroma_dir)).heartbeat()
        checks["vector_store"] = "ok"
    except Exception as e:
        checks["vector_store"] = f"error: {type(e).__name__}"
    checks["llm"] = "ok" if get_settings().google_api_key else "error: GOOGLE_API_KEY missing"
    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, **checks}
