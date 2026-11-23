from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.playlists import router as playlists_router
from app.api.v1.reference import router as reference_router
from app.api.v1.search import router as search_router
from app.api.v1.tracks import router as tracks_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(admin_router)
router.include_router(search_router)
router.include_router(tracks_router)
router.include_router(playlists_router)
router.include_router(reference_router)
