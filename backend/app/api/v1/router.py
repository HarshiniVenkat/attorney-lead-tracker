from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import auth, leads

api_router = APIRouter()

# Order matters: the public POST /leads and the authenticated GET /leads share
# a path, so both routers are mounted and FastAPI matches on method.
api_router.include_router(auth.router)
api_router.include_router(leads.public_router)
api_router.include_router(leads.router)
