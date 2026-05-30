"""Tests for log commands."""

import datetime

import pytest
from meta import (
    cmd_log_append, cmd_log_today, cmd_log_search,
    read_file,
)


class TestLogAppend:
    def test_append_basic(self, meta_repo):
        cmd_log_append(["action | topic | some notes"])
        content = read_file(meta_repo / "log.md")
        assert "action | topic | some notes" in content

    def test_append_without_notes(self, meta_repo):
        cmd_log_append(["action | topic"])
        content = read_file(meta_repo / "log.md")
        assert "action | topic" in content

    def test_append_empty_fails(self, meta_repo):
        with pytest.raises(SystemExit):
            cmd_log_append([""])

    def test_append_no_action_fails(self, meta_repo):
        with pytest.raises(SystemExit):
            cmd_log_append(["just notes"])

    def test_append_multiple_entries_same_day(self, meta_repo):
        cmd_log_append(["action | first | entry one"])
        cmd_log_append(["action | second | entry two"])
        content = read_file(meta_repo / "log.md")
        assert "entry one" in content
        assert "entry two" in content
        # Both should be under today's section
        today = datetime.date.today().isoformat()
        assert f"## {today}" in content

    def test_creates_today_section(self, meta_repo):
        cmd_log_append(["action | topic | creating today"])
        today = datetime.date.today().isoformat()
        content = read_file(meta_repo / "log.md")
        assert f"## {today}" in content

    def test_appends_to_existing_today(self, meta_repo):
        cmd_log_append(["action | a | first"])
        cmd_log_append(["action | b | second"])
        content = read_file(meta_repo / "log.md")
        # Second entry should be after first
        first_idx = content.index("first")
        second_idx = content.index("second")
        assert second_idx > first_idx


class TestLogToday:
    def test_shows_today_entries(self, meta_repo, capsys):
        cmd_log_append(["research | foo | test"])
        cmd_log_today()
        captured = capsys.readouterr().out
        assert "foo" in captured

    def test_no_entries(self, meta_repo, capsys):
        cmd_log_today()
        captured = capsys.readouterr().out
        assert "No entries" in captured


class TestLogSearch:
    def test_search_finds_match(self, meta_repo, capsys):
        cmd_log_append(["action | unique-topic | details"])
        cmd_log_search("unique-topic")
        captured = capsys.readouterr().out
        assert "unique-topic" in captured

    def test_search_no_match(self, meta_repo, capsys):
        cmd_log_search("does-not-exist")
        captured = capsys.readouterr().out
        assert "No log entries" in captured

    def test_search_case_insensitive(self, meta_repo, capsys):
        cmd_log_append(["action | CaseSensitive | details"])
        cmd_log_search("casesensitive")
        captured = capsys.readouterr().out
        assert "CaseSensitive" in captured


class TestLogArchiveNormalization:
    def test_duplicate_archive_markers_collapsed(self, meta_repo):
        """The cmd_log_append should normalize duplicate ## Archive markers."""
        # Create a log with duplicate Archive markers (like the corrupted state)
        content = read_file(meta_repo / "log.md")
        content += "\n## Archive\n## Archive\n## Archive\n"
        from meta import write_file
        write_file(meta_repo / "log.md", content)

        # Appending should collapse the duplicates
        cmd_log_append(["action | topic | after cleanup"])
        new_content = read_file(meta_repo / "log.md")
        assert new_content.count("## Archive") == 1, f"Expected 1 Archive marker, got {new_content.count('## Archive')}"

    def test_no_archive_marker_adds_one(self, meta_repo):
        """If log has no Archive marker, appending should add one."""
        content = read_file(meta_repo / "log.md")
        content = content.replace("## Archive", "")
        from meta import write_file
        write_file(meta_repo / "log.md", content)

        cmd_log_append(["action | topic | no archive before"])
        new_content = read_file(meta_repo / "log.md")
        assert "## Archive" in new_content
