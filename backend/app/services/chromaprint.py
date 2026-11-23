from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

FINGERPRINT_MATCH_THRESHOLD = 0.97


@dataclass(frozen=True)
class Fingerprint:
    compressed: str | None
    raw: list[int]
    duration_seconds: int | None


def fingerprint_similarity(left: list[int], right: list[int]) -> float:
    """Chromaprint similarity: 1 minus the bit error rate, best small alignment."""
    if not left or not right:
        return 0.0
    best = 0.0
    for shift in range(-4, 5):
        if shift >= 0:
            first = left
            second = right[shift:]
        else:
            first = left[-shift:]
            second = right
        length = min(len(first), len(second))
        if length == 0:
            continue
        mismatches = 0
        for index in range(length):
            mismatches += ((int(first[index]) ^ int(second[index])) & 0xFFFFFFFF).bit_count()
        score = 1.0 - (mismatches / (length * 32))
        if score > best:
            best = score
    return best


def fingerprints_match(left: list[int] | None, right: list[int] | None) -> bool:
    if not left or not right:
        return False
    return fingerprint_similarity(left, right) >= FINGERPRINT_MATCH_THRESHOLD


def _run_fpcalc(path: Path, *, raw: bool) -> dict[str, object] | None:
    binary = shutil.which("fpcalc")
    if binary is None:
        return None
    command = [binary, "-json", "-length", "120", str(path)]
    if raw:
        command.insert(2, "-raw")
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def fingerprint_file(path: Path) -> Fingerprint | None:
    compressed_payload = _run_fpcalc(path, raw=False)
    raw_payload = _run_fpcalc(path, raw=True)
    if compressed_payload is None and raw_payload is None:
        return None
    compressed = None
    if compressed_payload is not None and isinstance(compressed_payload.get("fingerprint"), str):
        compressed = str(compressed_payload["fingerprint"])
    raw_values: list[int] = []
    raw_fingerprint = raw_payload.get("fingerprint") if raw_payload is not None else None
    if isinstance(raw_fingerprint, list):
        for item in raw_fingerprint:
            if isinstance(item, int):
                raw_values.append(item)
    duration = None
    source = raw_payload or compressed_payload or {}
    raw_duration = source.get("duration")
    if isinstance(raw_duration, int | float):
        duration = int(raw_duration)
    if compressed is None and not raw_values:
        return None
    return Fingerprint(compressed=compressed, raw=raw_values, duration_seconds=duration)
