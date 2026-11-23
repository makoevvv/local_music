from __future__ import annotations

import gzip
import os
import plistlib
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_backup_db_writes_gzip_and_drops_dumps_older_than_seven_days(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text("#!/bin/sh\nprintf 'dump-ok\\n'\n", encoding="utf-8")
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old_dump = backup_dir / "db_2000-01-01.sql.gz"
    old_dump.write_bytes(b"old")
    old_stamp = 10 * 24 * 60 * 60
    now = old_dump.stat().st_mtime
    os.utime(old_dump, (now - old_stamp, now - old_stamp))
    recent = backup_dir / "db_2099-01-01.sql.gz"
    recent.write_bytes(gzip.compress(b"keep"))

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["BACKUP_DIR"] = str(backup_dir)
    env["POSTGRES_USER"] = "music"
    env["POSTGRES_DB"] = "local_music"

    subprocess.run(
        ["bash", str(ROOT / "infra" / "scripts" / "backup_db.sh")],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert not old_dump.exists()
    assert recent.exists()
    fresh = [path for path in backup_dir.glob("db_*.sql.gz") if path != recent]
    assert len(fresh) == 1
    assert gzip.decompress(fresh[0].read_bytes()) == b"dump-ok\n"


def test_cron_matches_the_infrastructure_schedule() -> None:
    text = (ROOT / "infra" / "cron" / "local-music").read_text(encoding="utf-8")
    assert "0 3 * * *  cd ~/srv/local-music && ./infra/scripts/backup_db.sh" in text
    assert "15 3 * * * cd ~/srv/local-music && ./infra/scripts/export_index.sh" in text
    assert "30 4 * * * cd ~/srv/local-music && ./infra/scripts/library_maintenance.sh" in text


def test_launchd_jobs_use_the_same_clock_times() -> None:
    expected = {
        "com.localmusic.backup-db.plist": ("backup_db.sh", 3, 0),
        "com.localmusic.export-index.plist": ("export_index.sh", 3, 15),
        "com.localmusic.library-maintenance.plist": ("library_maintenance.sh", 4, 30),
    }
    for name, (script, hour, minute) in expected.items():
        payload = plistlib.loads((ROOT / "infra" / "launchd" / name).read_bytes())
        slot = payload["StartCalendarInterval"]
        assert slot["Hour"] == hour
        assert slot["Minute"] == minute
        assert payload["ProgramArguments"] == [f"__REPO_ROOT__/infra/scripts/{script}"]
        assert payload["WorkingDirectory"] == "__REPO_ROOT__"
