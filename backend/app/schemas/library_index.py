from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class IndexExportRequest(BaseModel):
    minimal: bool = False
    include_covers: bool = False
    include_secrets: bool = False
    no_plays: bool = False
    filename: str | None = None


class IndexExportResponse(BaseModel):
    job_id: str | None = None
    filename: str
    status: Literal["queued", "completed"] = "queued"
    track_count: int | None = None
    path: str | None = None


class IndexExportItem(BaseModel):
    filename: str
    size_bytes: int
    modified_at: str | None = None


class IndexImportRequest(BaseModel):
    filename: str
    mode: Literal["skip-existing", "overwrite", "mirror"] = "skip-existing"


class IndexImportResponse(BaseModel):
    imported_tracks: int
    skipped_tracks: int
    overwritten_tracks: int
    sha256_mapped: int
    warnings: list[str] = Field(default_factory=list)


class LibraryRestoreRequest(BaseModel):
    strategy: str = "best-source-first"
    concurrency: int = Field(default=2, ge=1, le=8)
    dry_run: bool = False
    track_ids: list[uuid.UUID] | None = None


class LibraryRestoreResponse(BaseModel):
    job_id: str | None = None
    status: Literal["queued", "completed"] = "queued"
    attempted: int | None = None
    restored: int | None = None
    unrecoverable: int | None = None
    skipped: int | None = None
    dry_run: bool = False
    details: list[dict[str, Any]] = Field(default_factory=list)


class LibraryHealthResponse(BaseModel):
    track_count: int
    missing_files: int
    unrecoverable: int
    stale_sources: int
    sources_by_status: dict[str, int]
