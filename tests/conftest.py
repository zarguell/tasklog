"""Pytest fixtures for meta CLI tests."""

import os
from pathlib import Path
from typing import Generator

import pytest

# ── Template repos ───────────────────────────────────────────

FRESH_TODO = """# TODO

High-level project backlog. Top of each section = highest priority.

## 🔜 Next



## 🚧 In Progress



## 📋 Backlog

- [ ] **Example task one**
- [ ] **Example task two**

## 🚫 Blocked

- [ ] **Example blocked task**

## ✅ Done



## 🗄️ Archived


"""

FRESH_LOG = """# Changelog

> Chronological record of decisions and actions. Append-only.

## Archive

"""

AGENTS_MD = """# AGENTS.md — Meta Repo Operating Manual

Placeholder for tests.
"""


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def meta_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a fresh temporary tasklog repo. Sets TASKLOG_REPO env var."""
    repo = tmp_path / "meta_repo"
    repo.mkdir(parents=True)

    (repo / "AGENTS.md").write_text(AGENTS_MD)
    (repo / "TODO.md").write_text(FRESH_TODO)
    (repo / "log.md").write_text(FRESH_LOG)
    ctx_dir = repo / "context"
    ctx_dir.mkdir()

    # Set env var so find_repo() resolves to this temp repo
    monkeypatch.setenv("TASKLOG_REPO", str(repo))

    # Init git so git_commit works
    import subprocess
    subprocess.run(["git", "init", "-q", str(repo)], capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@test"], capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], capture_output=True)
    return repo


@pytest.fixture
def repo_env(meta_repo: Path) -> Path:
    """Alias — meta_repo already sets META_REPO. Provided for clarity."""
    return meta_repo


@pytest.fixture
def populated_repo(meta_repo: Path) -> Path:
    """Repo with diverse content for testing status/session/output."""
    import subprocess
    from meta import (
        cmd_todo_add, cmd_todo_start, cmd_todo_block, cmd_todo_done,
        cmd_todo_note,
    )

    cmd_todo_add(meta_repo, "Feature X")
    cmd_todo_add(meta_repo, "Feature Y")
    cmd_todo_add(meta_repo, "Bugfix Z")
    cmd_todo_start(meta_repo, "Feature X")
    cmd_todo_block(meta_repo, "Example blocked task")
    cmd_todo_done(meta_repo, "Example task one")
    cmd_todo_note(meta_repo, "Feature X", "Design phase")

    # Add a log entry
    from meta import cmd_log_append
    cmd_log_append(["improvement | tests | Added test suite"])

    # Commit all changes
    subprocess.run(["git", "-C", str(meta_repo), "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", str(meta_repo), "commit", "-m", "populated"], capture_output=True)

    return meta_repo
