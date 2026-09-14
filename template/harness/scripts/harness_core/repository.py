"""Repository paths, persistence, Git, and implementation fingerprints."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


VOLATILE_PATHS = {
    "harness/features.json",
    "harness/progress/current.md",
    "harness/progress/history.md",
    "harness/progress/verification.json",
}


def run_git(root: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run Git without a shell and capture UTF-8 text."""
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        shell=False,
        check=False,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise HarnessError(f"git {' '.join(args)} failed: {detail}")
    return result


def paths(root: Path) -> dict[str, Path]:
    """Return canonical harness paths for a repository root."""
    harness = root / "harness"
    progress = harness / "progress"
    return {
        "root": root,
        "harness": harness,
        "config": harness / "config.json",
        "features": harness / "features.json",
        "specs": harness / "specs",
        "progress": progress,
        "current": progress / "current.md",
        "history": progress / "history.md",
        "reviews": progress / "reviews",
        "verification": progress / "verification.json",
    }


def git_is_clean(root: Path) -> bool:
    """Return whether tracked, staged, and untracked state is clean."""
    return not run_git(root, ["status", "--porcelain"]).stdout


def is_volatile(path: str) -> bool:
    """Identify coordinator-owned evidence excluded from implementation identity."""
    return path in VOLATILE_PATHS or path.startswith("harness/progress/reviews/")


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp without fractional seconds."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def implementation_fingerprint(root: Path, baseline: str) -> str:
    """Hash repository content changed since approval, excluding volatile evidence."""
    digest = hashlib.sha256()
    for relative in changed_paths(root, baseline):
        if is_volatile(relative):
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        path = root / relative
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<deleted>")
        digest.update(b"\0")
    return digest.hexdigest()


def discover_root(start: Path | None = None) -> Path:
    """Find the enclosing Git root."""
    location = (start or Path.cwd()).resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=location,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        shell=False,
        check=False,
    )
    if result.returncode != 0:
        raise HarnessError("The harness must run inside a Git repository.")
    return Path(result.stdout.strip()).resolve()


def json_write(path: Path, value: Any) -> None:
    """Write stable, human-readable JSON atomically."""
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def changed_paths(root: Path, baseline: str) -> list[str]:
    """Return all tracked changes from baseline plus current untracked files."""
    tracked = run_git(root, ["diff", "--name-only", "--diff-filter=ACDMRTUXB", baseline, "--"]).stdout.splitlines()
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"]).stdout.splitlines()
    return sorted({item.replace("\\", "/") for item in [*tracked, *untracked] if item})


def atomic_write(path: Path, text: str) -> None:
    """Replace a UTF-8 text file atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def normalized_relative(root: Path, candidate: Path) -> str:
    """Return a slash-normalized repository-relative path."""
    return candidate.resolve().relative_to(root.resolve()).as_posix()


class HarnessError(Exception):
    """A user-correctable harness invariant or command failure."""


def json_load(path: Path) -> dict[str, Any]:
    """Load one JSON object with a useful error on malformed input."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HarnessError(f"Required file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HarnessError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HarnessError(f"Expected a JSON object in {path}")
    return value
