from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.catalog import GenrePublic, LanguagePublic
from app.services.catalog import CatalogService

router = APIRouter(tags=["reference"])


@router.get("/genres", response_model=list[GenrePublic])
async def list_genres(_user: CurrentUser, session: DbSession) -> list[GenrePublic]:
    genres = await CatalogService(session).list_genres()
    return [GenrePublic.model_validate(item) for item in genres]


@router.get("/languages", response_model=list[LanguagePublic])
async def list_languages(_user: CurrentUser, session: DbSession) -> list[LanguagePublic]:
    languages = await CatalogService(session).list_languages()
    return [LanguagePublic.model_validate(item) for item in languages]
