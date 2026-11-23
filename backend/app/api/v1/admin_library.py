from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.deps import CurrentAdmin, CurrentMaster, DbSession
from app.core.rq_queue import get_queue
from app.schemas.library_index import (
    IndexExportItem,
    IndexExportRequest,
    IndexExportResponse,
    IndexImportRequest,
    IndexImportResponse,
    LibraryHealthResponse,
    LibraryRestoreRequest,
    LibraryRestoreResponse,
)
from app.services.library_index import (
    ExportOptions,
    LibraryIndexService,
    exports_root,
    list_export_files,
    resolve_export_file,
)
from app.workers.tasks import export_index_job, restore_library_job

router = APIRouter(prefix="/admin", tags=["admin-library"])


def _default_export_filename(*, minimal: bool) -> str:
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    if minimal:
        return f"library-{stamp}.jsonl.gz"
    return f"library-{stamp}.tar.gz"


@router.post("/index/export", response_model=IndexExportResponse)
async def export_index(
    payload: IndexExportRequest,
    _master: CurrentMaster,
    session: DbSession,
) -> IndexExportResponse:
    filename = payload.filename or _default_export_filename(minimal=payload.minimal)
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")

    # Minimal exports run inline (small, easy to test without RQ).
    if payload.minimal:
        out = exports_root() / filename
        result = await LibraryIndexService(session).export_index(
            ExportOptions(
                out=out,
                minimal=True,
                include_covers=False,
                include_secrets=payload.include_secrets,
                no_plays=True,
            )
        )
        return IndexExportResponse(
            filename=filename,
            status="completed",
            track_count=result.track_count,
            path=str(result.path),
        )

    queue = get_queue()
    job = queue.enqueue(
        export_index_job,
        filename=filename,
        minimal=payload.minimal,
        include_covers=payload.include_covers,
        include_secrets=payload.include_secrets,
        no_plays=payload.no_plays,
        job_timeout=1800,
    )
    return IndexExportResponse(job_id=job.id, filename=filename, status="queued")


@router.get("/index/exports", response_model=list[IndexExportItem])
async def list_exports(_master: CurrentMaster) -> list[IndexExportItem]:
    return [IndexExportItem.model_validate(item) for item in list_export_files()]


@router.get("/index/exports/{filename}")
async def download_export(filename: str, _master: CurrentMaster) -> FileResponse:
    try:
        path = resolve_export_file(filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export not found"
        ) from exc
    return FileResponse(path=path, filename=path.name, media_type="application/gzip")


@router.post("/index/import", response_model=IndexImportResponse)
async def import_index(
    payload: IndexImportRequest,
    _master: CurrentMaster,
    session: DbSession,
) -> IndexImportResponse:
    try:
        archive = resolve_export_file(payload.filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export not found"
        ) from exc

    result = await LibraryIndexService(session).import_index(archive, mode=payload.mode)
    return IndexImportResponse(
        imported_tracks=result.imported_tracks,
        skipped_tracks=result.skipped_tracks,
        overwritten_tracks=result.overwritten_tracks,
        sha256_mapped=result.sha256_mapped,
        warnings=result.warnings,
    )


@router.post("/library/restore", response_model=LibraryRestoreResponse)
async def restore_library(
    payload: LibraryRestoreRequest,
    _master: CurrentMaster,
    session: DbSession,
) -> LibraryRestoreResponse:
    if payload.dry_run:
        result = await LibraryIndexService(session).restore_library(
            strategy=payload.strategy,
            concurrency=payload.concurrency,
            dry_run=True,
            track_ids=payload.track_ids,
        )
        return LibraryRestoreResponse(
            status="completed",
            attempted=result.attempted,
            restored=result.restored,
            unrecoverable=result.unrecoverable,
            skipped=result.skipped,
            dry_run=True,
            details=result.details,
        )

    queue = get_queue()
    job = queue.enqueue(
        restore_library_job,
        strategy=payload.strategy,
        concurrency=payload.concurrency,
        dry_run=False,
        track_ids=[str(item) for item in payload.track_ids] if payload.track_ids else None,
        job_timeout=3600,
    )
    return LibraryRestoreResponse(job_id=job.id, status="queued", dry_run=False)


@router.get("/library/health", response_model=LibraryHealthResponse)
async def library_health(_admin: CurrentAdmin, session: DbSession) -> LibraryHealthResponse:
    data = await LibraryIndexService(session).library_health()
    return LibraryHealthResponse.model_validate(data)
