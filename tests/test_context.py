"""Tests for context commands."""

import pytest
from meta import cmd_context_create, cmd_context_list, cmd_context_archive


class TestContextCreate:
    def test_create_new(self, meta_repo):
        cmd_context_create(meta_repo, "test-topic")
        assert (meta_repo / "context" / "test-topic.md").exists()

    def test_create_with_spaces(self, meta_repo):
        cmd_context_create(meta_repo, "My Big Topic")
        assert (meta_repo / "context" / "my-big-topic.md").exists()

    def test_create_duplicate(self, meta_repo, capsys):
        cmd_context_create(meta_repo, "test-topic")
        cmd_context_create(meta_repo, "test-topic")
        captured = capsys.readouterr().out
        assert "already exists" in captured

    def test_create_with_uppercase(self, meta_repo):
        cmd_context_create(meta_repo, "UPPERCASE Topic")
        assert (meta_repo / "context" / "uppercase-topic.md").exists()


class TestContextList:
    def test_list_empty(self, meta_repo, capsys):
        cmd_context_list(meta_repo)
        captured = capsys.readouterr().out
        assert "No context" in captured

    def test_list_with_files(self, meta_repo, capsys):
        cmd_context_create(meta_repo, "topic-a")
        cmd_context_create(meta_repo, "topic-b")
        cmd_context_list(meta_repo)
        captured = capsys.readouterr().out
        assert "topic-a" in captured
        assert "topic-b" in captured

    def test_list_shows_archived_count(self, meta_repo, capsys):
        cmd_context_create(meta_repo, "active-topic")
        cmd_context_archive(meta_repo, "active-topic")
        cmd_context_list(meta_repo)
        captured = capsys.readouterr().out
        assert "archived" in captured


class TestContextArchive:
    def test_archive_moves_file(self, meta_repo):
        cmd_context_create(meta_repo, "to-archive")
        cmd_context_archive(meta_repo, "to-archive")
        assert not (meta_repo / "context" / "to-archive.md").exists()
        assert (meta_repo / "context" / "_archived" / "to-archive.md").exists()

    def test_archive_nonexistent(self, meta_repo):
        with pytest.raises(SystemExit):
            cmd_context_archive(meta_repo, "does-not-exist")
