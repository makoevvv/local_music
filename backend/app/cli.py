from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from collections.abc import Awaitable, Callable
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

    import_track = subparsers.add_parser("import-track", help="Import local audio file into catalog")
    import_track.add_argument("--file", required=True)
    import_track.add_argument("--title", required=True)
    import_track.add_argument("--artist", required=True)
    import_track.add_argument("--album", default=None)
    import_track.add_argument("--user-id", required=True)

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
    from pathlib import Path

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

    parser.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()
