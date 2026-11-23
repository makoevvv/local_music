from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.invite import Invite
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.auth import AdminService, MasterBootstrapService

T = TypeVar("T")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_master = subparsers.add_parser("init-master", help="Create the one-time master account")
    init_master.add_argument("--email", required=True)
    init_master.add_argument("--username", required=True)
    init_master.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read password from stdin",
    )

    create_invite = subparsers.add_parser("create-invite", help="Create invite code")
    create_invite.add_argument("--created-by-user-id", required=True)
    create_invite.add_argument("--expires-in-days", type=int, default=None)

    reset_master = subparsers.add_parser(
        "reset-master-password",
        help="Reset master password from stdin",
    )
    reset_master.add_argument("--password-stdin", action="store_true")

    import_track = subparsers.add_parser(
        "import-track", help="Import local audio file into catalog"
    )
    import_track.add_argument("--file", required=True)
    import_track.add_argument("--title", required=True)
    import_track.add_argument("--artist", required=True)
    import_track.add_argument("--album", default=None)
    import_track.add_argument("--user-id", required=True)

    index_parser = subparsers.add_parser("index", help="Library index export/import")
    index_sub = index_parser.add_subparsers(dest="index_command", required=True)

    index_export = index_sub.add_parser("export", help="Export library index")
    index_export.add_argument("--out", required=True)
    index_export.add_argument("--minimal", action="store_true")
    index_export.add_argument("--include-covers", action="store_true")
    index_export.add_argument("--include-secrets", action="store_true")
    index_export.add_argument("--no-plays", action="store_true")

    index_import = index_sub.add_parser("import", help="Import library index")
    index_import.add_argument("--in", dest="archive", required=True)
    index_import.add_argument(
        "--mode",
        choices=["skip-existing", "overwrite", "mirror"],
        default="skip-existing",
    )

    library_parser = subparsers.add_parser("library", help="Library restore operations")
    library_sub = library_parser.add_subparsers(dest="library_command", required=True)
    library_restore = library_sub.add_parser("restore", help="Restore audio from track_sources")
    library_restore.add_argument("--strategy", default="best-source-first")
    library_restore.add_argument("--concurrency", type=int, default=2)
    library_restore.add_argument("--dry-run", action="store_true")

    verify = subparsers.add_parser("verify-sources", help="Probe track_sources availability")
    verify.add_argument("--limit", type=int, default=200)

    return parser


async def _with_session(coro: Callable[[AsyncSession], Awaitable[T]]) -> T:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        try:
            result = await coro(session)
            return result
        finally:
            await engine.dispose()


async def _cmd_init_master(args: argparse.Namespace) -> int:
    if not args.password_stdin:
        print("init-master requires --password-stdin", file=sys.stderr)
        return 1
    password = getpass.getpass("Master password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match", file=sys.stderr)
        return 1

    async def run(session: AsyncSession) -> User:
        service = MasterBootstrapService(session)
        user = await service.init_master(
            email=args.email,
            username=args.username,
            password=password,
        )
        return user

    try:
        user = await _with_session(run)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Master account created: {user.email} ({user.id})")
    return 0


async def _cmd_create_invite(args: argparse.Namespace) -> int:
    import uuid

    from app.schemas.auth import CreateInviteRequest

    creator_id = uuid.UUID(args.created_by_user_id)

    async def run(session: AsyncSession) -> Invite:
        users = UserRepository(session)
        creator = await users.get_by_id(creator_id)
        if creator is None:
            raise RuntimeError("Creator user not found")
        invite = await AdminService(session).create_invite(
            creator,
            CreateInviteRequest(expires_in_days=args.expires_in_days),
        )
        return invite

    try:
        invite = await _with_session(run)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Invite created: {invite.code}")
    if invite.expires_at:
        print(f"Expires at: {invite.expires_at.isoformat()}")
    return 0


async def _cmd_reset_master_password(args: argparse.Namespace) -> int:
    if not args.password_stdin:
        print("reset-master-password requires --password-stdin", file=sys.stderr)
        return 1
    password = getpass.getpass("New master password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match", file=sys.stderr)
        return 1

    async def run(session: AsyncSession) -> User:
        return await MasterBootstrapService(session).reset_master_password(password)

    try:
        user = await _with_session(run)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Master password updated for {user.email}")
    return 0


async def _cmd_import_track(args: argparse.Namespace) -> int:
    import uuid

    from app.models.catalog import Track
    from app.services.catalog import CatalogService

    source = Path(args.file)
    if not source.exists():
        print(f"File not found: {source}", file=sys.stderr)
        return 1
    user_id = uuid.UUID(args.user_id)

    async def run(session: AsyncSession) -> Track:
        return await CatalogService(session).import_local_track(
            source_file=source,
            title=args.title,
            artist_name=args.artist,
            album_title=args.album,
            added_by_user_id=user_id,
        )

    track: Track = await _with_session(run)
    print(f"Track imported: {track.title} ({track.id})")
    return 0


async def _cmd_index_export(args: argparse.Namespace) -> int:
    from app.services.library_index import ExportOptions, LibraryIndexService

    out = Path(args.out)

    async def run(session: AsyncSession) -> str:
        result = await LibraryIndexService(session).export_index(
            ExportOptions(
                out=out,
                minimal=args.minimal,
                include_covers=args.include_covers,
                include_secrets=args.include_secrets,
                no_plays=args.no_plays,
            )
        )
        return f"{result.path} tracks={result.track_count} sha256={result.sha256}"

    message = await _with_session(run)
    print(message)
    return 0


async def _cmd_index_import(args: argparse.Namespace) -> int:
    from app.services.library_index import LibraryIndexService

    archive = Path(args.archive)
    if not archive.exists():
        print(f"Archive not found: {archive}", file=sys.stderr)
        return 1

    async def run(session: AsyncSession) -> str:
        result = await LibraryIndexService(session).import_index(archive, mode=args.mode)
        return (
            f"imported={result.imported_tracks} skipped={result.skipped_tracks} "
            f"overwritten={result.overwritten_tracks} sha256_mapped={result.sha256_mapped}"
        )

    message = await _with_session(run)
    print(message)
    return 0


async def _cmd_library_restore(args: argparse.Namespace) -> int:
    from app.services.library_index import LibraryIndexService

    async def run(session: AsyncSession) -> str:
        result = await LibraryIndexService(session).restore_library(
            strategy=args.strategy,
            concurrency=args.concurrency,
            dry_run=args.dry_run,
        )
        return (
            f"attempted={result.attempted} restored={result.restored} "
            f"unrecoverable={result.unrecoverable} skipped={result.skipped} "
            f"dry_run={result.dry_run}"
        )

    message = await _with_session(run)
    print(message)
    return 0


def _cmd_verify_sources(args: argparse.Namespace) -> int:
    from app.workers.tasks import verify_sources_job

    result = verify_sources_job(limit=args.limit)
    print(f"checked={result['checked']} updated={result['updated']}")
    return 0


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "init-master":
        raise SystemExit(asyncio.run(_cmd_init_master(args)))
    if args.command == "create-invite":
        raise SystemExit(asyncio.run(_cmd_create_invite(args)))
    if args.command == "reset-master-password":
        raise SystemExit(asyncio.run(_cmd_reset_master_password(args)))
    if args.command == "import-track":
        raise SystemExit(asyncio.run(_cmd_import_track(args)))
    if args.command == "index" and args.index_command == "export":
        raise SystemExit(asyncio.run(_cmd_index_export(args)))
    if args.command == "index" and args.index_command == "import":
        raise SystemExit(asyncio.run(_cmd_index_import(args)))
    if args.command == "library" and args.library_command == "restore":
        raise SystemExit(asyncio.run(_cmd_library_restore(args)))
    if args.command == "verify-sources":
        raise SystemExit(_cmd_verify_sources(args))

    parser.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()
