from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_local_repository_is_synced_with_origin_main() -> None:
    _run_git("fetch", "origin", "main")

    status_porcelain = _run_git("status", "--porcelain")
    assert status_porcelain == "", "Working tree has uncommitted or untracked changes."

    local_head = _run_git("rev-parse", "HEAD")
    remote_main_head = _run_git("rev-parse", "origin/main")
    merge_base = _run_git("merge-base", "HEAD", "origin/main")

    assert local_head == remote_main_head, (
        "Local HEAD and origin/main are different; repository is not synced."
    )
    assert merge_base == local_head, (
        "Local branch has diverged from origin/main; repository is not synced."
    )
