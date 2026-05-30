"""Tests for status and session commands."""

import pytest
from meta import cmd_status, cmd_session


class TestStatus:
    def test_compact_default(self, meta_repo, capsys):
        cmd_status(meta_repo)
        captured = capsys.readouterr().out
        # Compact format starts with 'status —'
        assert captured.startswith("status —"), f"Expected compact format, got: {captured}"
        # Should show counts
        assert "📋" in captured or "🚧" in captured or "🔜" in captured or "🚫" in captured

    def test_verbose_shows_log(self, meta_repo, capsys):
        cmd_status(meta_repo, verbose=True)
        captured = capsys.readouterr().out
        assert "━━━" in captured
        assert "total pending" in captured

    def test_verbose_shows_recent_log(self, meta_repo, capsys):
        from meta import cmd_log_append
        cmd_log_append(["action | test-topic | log entry for status"])
        cmd_status(meta_repo, verbose=True)
        captured = capsys.readouterr().out
        assert "test-topic" in captured

    def test_populated_shows_in_progress(self, populated_repo, capsys):
        cmd_status(populated_repo)
        captured = capsys.readouterr().out
        assert "Feature X" in captured
        assert "🚧" in captured


class TestSession:
    def test_compact_default(self, meta_repo, capsys):
        cmd_session(meta_repo)
        captured = capsys.readouterr().out
        # Compact format starts with 'meta '
        assert captured.startswith("meta "), f"Expected compact format, got: {captured}"

    def test_verbose_box_art(self, meta_repo, capsys):
        cmd_session(meta_repo, verbose=True)
        captured = capsys.readouterr().out
        assert "┏━━━━" in captured
        assert "┗━━━━" in captured
        assert "meta session" in captured

    def test_verbose_shows_done_count(self, meta_repo, capsys):
        cmd_session(meta_repo, verbose=True)
        captured = capsys.readouterr().out
        assert "✅ Done" in captured or "Done: 0" in captured

    def test_populated_shows_in_progress(self, populated_repo, capsys):
        cmd_session(populated_repo)
        captured = capsys.readouterr().out
        assert "Feature X" in captured

    def test_populated_verbose_full(self, populated_repo, capsys):
        cmd_session(populated_repo, verbose=True)
        captured = capsys.readouterr().out
        assert "Feature X" in captured
        assert "Bugfix Z" in captured
        assert "Example blocked task" in captured
        assert "Example task" in captured  # done task
