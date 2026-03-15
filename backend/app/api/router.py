"""Top-level API router that aggregates all v1 sub-routers."""

from fastapi import APIRouter

from app.api.exports import router as exports_router
from app.api.jobs import router as jobs_router
from app.api.niches import router as niches_router
from app.api.products import router as products_router
from app.api.recommendations import router as recommendations_router
from app.api.settings import router as settings_router

router = APIRouter()

# ── Sub-routers ──────────────────────────────────────────────────────────
router.include_router(niches_router)
router.include_router(products_router)
router.include_router(recommendations_router)
router.include_router(settings_router)
router.include_router(exports_router)
router.include_router(jobs_router)
