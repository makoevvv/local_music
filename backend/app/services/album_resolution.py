from __future__ import annotations

from typing import Any

from app.schemas.upload import AlbumResolution
from app.services.verification.lookup import fetch_recording_releases, search_musicbrainz

_ALBUM_TYPES = {"Album", "EP"}


def _release_group(release: dict[str, Any]) -> dict[str, Any]:
    group = release.get("release-group") or release.get("release_group") or {}
    return group if isinstance(group, dict) else {}


def _primary_type(release: dict[str, Any]) -> str | None:
    primary = _release_group(release).get("primary-type") or _release_group(release).get(
        "primary_type"
    )
    return str(primary) if isinstance(primary, str) else None


def _date_key(release: dict[str, Any]) -> tuple[int, int, int]:
    raw = release.get("date")
    if not isinstance(raw, str) or not raw:
        return (9999, 12, 31)
    parts = raw.split("-")
    numbers: list[int] = []
    for part in parts[:3]:
        if part.isdigit():
            numbers.append(int(part))
        else:
            break
    while len(numbers) < 3:
        numbers.append(1)
    return (numbers[0], numbers[1], numbers[2])


def _year(release: dict[str, Any]) -> int | None:
    year = _date_key(release)[0]
    if year >= 9999:
        return None
    return year


def _title(release: dict[str, Any], fallback: str) -> str:
    group_title = _release_group(release).get("title")
    if isinstance(group_title, str) and group_title.strip():
        return group_title.strip()
    release_title = release.get("title")
    if isinstance(release_title, str) and release_title.strip():
        return release_title.strip()
    return fallback


def _group_mbid(release: dict[str, Any]) -> str | None:
    group_id = _release_group(release).get("id")
    return str(group_id) if isinstance(group_id, str) and group_id else None


def _cover_url(release_group_mbid: str | None) -> str | None:
    if not release_group_mbid:
        return None
    return f"https://coverartarchive.org/release-group/{release_group_mbid}/front"


def unresolved_album(track_title: str, recording_mbid: str | None = None) -> AlbumResolution:
    return AlbumResolution(
        title=track_title,
        is_single=False,
        unresolved=True,
        recording_mbid=recording_mbid,
    )


def decision_from_releases(
    releases: list[dict[str, Any]],
    track_title: str,
    recording_mbid: str | None = None,
) -> AlbumResolution:
    """Pick a real album/EP, a confirmed single, or an unresolved container.

    `is_single` is true only when every release-group primary type is Single.
    Anything unresolved stays `is_single=false` so a later reconcile can move it.
    """
    if not releases:
        return unresolved_album(track_title, recording_mbid)

    typed = [(release, _primary_type(release)) for release in releases]
    albumish = [item for item in typed if item[1] in _ALBUM_TYPES]
    if albumish:
        release = min((item[0] for item in albumish), key=_date_key)
        group_mbid = _group_mbid(release)
        return AlbumResolution(
            title=_title(release, track_title),
            release_group_mbid=group_mbid,
            release_year=_year(release),
            is_single=False,
            unresolved=False,
            cover_url=_cover_url(group_mbid),
            recording_mbid=recording_mbid,
        )

    if typed and all(primary == "Single" for _, primary in typed):
        release = min((item[0] for item in typed), key=_date_key)
        group_mbid = _group_mbid(release)
        return AlbumResolution(
            title=track_title,
            release_group_mbid=group_mbid,
            release_year=_year(release),
            is_single=True,
            unresolved=False,
            cover_url=_cover_url(group_mbid),
            recording_mbid=recording_mbid,
        )

    return unresolved_album(track_title, recording_mbid)


def resolve_album(*, artist: str, title: str, recording_mbid: str | None) -> AlbumResolution:
    """AcoustID recording mbid, else a MusicBrainz search at score >= 90, else unresolved."""
    releases: list[dict[str, Any]] = []
    used = recording_mbid
    if used:
        releases = fetch_recording_releases(used)
    if not releases and artist.strip() and title.strip():
        score, found_mbid, _, _ = search_musicbrainz(artist, title)
        if found_mbid and score >= 0.9:
            used = found_mbid
            releases = fetch_recording_releases(found_mbid)
    if not releases:
        return unresolved_album(title or "Unknown", used)
    return decision_from_releases(releases, title or "Unknown", used)
