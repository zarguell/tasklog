"""End-to-end tests for CLI dispatch via subprocess."""

import subprocess
import sys
from pathlib import Path


def test_cli_help():
    """meta --help should print usage."""
    result = subprocess.run(
        [sys.executable, "-m", "meta", "--help"],
        capture_output=True, text=True,
        cwd="/tmp/meta",
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "session" in result.stdout
    assert "status" in result.stdout


def test_cli_session(meta_repo, capsys):
    """meta session should output compact format."""
    result = subprocess.run(
        [sys.executable, "-m", "meta", "session"],
        capture_output=True, text=True,
        cwd=str(meta_repo),
    )
    assert result.returncode == 0
    assert result.stdout.startswith("meta ")


def test_cli_session_verbose(meta_repo, capsys):
    """meta session --verbose should output box art."""
    result = subprocess.run(
        [sys.executable, "-m", "meta", "session", "--verbose"],
        capture_output=True, text=True,
        cwd=str(meta_repo),
    )
    assert result.returncode == 0
    assert "┏━━━━" in result.stdout


def test_cli_status(meta_repo, capsys):
    """meta status should output compact format."""
    result = subprocess.run(
        [sys.executable, "-m", "meta", "status"],
        capture_output=True, text=True,
        cwd=str(meta_repo),
    )
    assert result.returncode == 0
    assert result.stdout.startswith("status —")


def test_cli_todo_ls(meta_repo, capsys):
    """meta todo ls should list tasks."""
    result = subprocess.run(
        [sys.executable, "-m", "meta", "todo", "ls"],
        capture_output=True, text=True,
        cwd=str(meta_repo),
    )
    assert result.returncode == 0
    assert "Example task" in result.stdout


def test_cli_todo_add(meta_repo, capsys):
    """meta todo add should work."""
    result = subprocess.run(
        [sys.executable, "-m", "meta", "todo", "add", "CLI-added task"],
        capture_output=True, text=True, cwd=str(meta_repo),
    )
    assert result.returncode == 0
    assert "Added" in result.stdout
    # Verify it was persisted
    content = (meta_repo / "TODO.md").read_text()
    assert "CLI-added task" in content


def test_cli_context_list(meta_repo, capsys):
    """meta context list should work."""
    result = subprocess.run(
        [sys.executable, "-m", "meta", "context", "list"],
        capture_output=True, text=True, cwd=str(meta_repo),
    )
    assert result.returncode == 0


def test_cli_log_append(meta_repo, capsys):
    """meta log should work."""
    result = subprocess.run(
        [sys.executable, "-m", "meta", "log",
         "action | cli-test | via subprocess"],
        capture_output=True, text=True, cwd=str(meta_repo),
    )
    assert result.returncode == 0
    assert "Logged" in result.stdout
