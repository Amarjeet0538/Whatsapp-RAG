from fastapi import FastAPI

from app.errors import APIError, api_error_handler
from app.routers import groups, health

app = FastAPI(title="WhatsApp RAG Assistant", version="0.1.0")
app.add_exception_handler(APIError, api_error_handler)
app.include_router(health.router, prefix="/api/v1")
app.include_router(groups.router, prefix="/api/v1")
