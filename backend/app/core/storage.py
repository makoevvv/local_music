from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from app.core.config import settings


def storage_root() -> Path:
    root = Path(settings.storage_local_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def track_storage_path(track_id: uuid.UUID, extension: str) -> Path:
    prefix = str(track_id).replace("-", "")[:2]
    directory = storage_root() / "tracks" / prefix
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{track_id}.{extension.lstrip('.')}"


def resolve_track_file(relative_path: str) -> Path:
    path = Path(relative_path)
    resolved = path if path.is_absolute() else storage_root() / path
    if not resolved.exists():
        msg = f"Track file not found: {resolved}"
        raise FileNotFoundError(msg)
    return resolved


def copy_track_file(source: Path, track_id: uuid.UUID) -> tuple[str, str, int, str]:
    extension = source.suffix.lstrip(".") or "mp3"
    destination = track_storage_path(track_id, extension)
    shutil.copy2(source, destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    relative = str(destination.relative_to(storage_root()))
    return relative, extension, destination.stat().st_size, digest
