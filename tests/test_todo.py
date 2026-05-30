"""Tests for todo commands."""

import re
import pytest
from meta import (
    cmd_todo_add, cmd_todo_done, cmd_todo_start, cmd_todo_block,
    cmd_todo_unblock, cmd_todo_move, cmd_todo_bump, cmd_todo_rm,
    cmd_todo_ls, cmd_todo_prune, cmd_todo_note, cmd_todo_notes,
    cmd_todo_ls, read_file,
    SECTION_HEADERS, fail,
)


def _task_in_section(repo, task, section):
    """Check if a task exists in a given section."""
    from meta import _parse_todo_sections
    sections = _parse_todo_sections(repo)
    titles = [t for t, _ in sections.get(section, [])]
    return task in titles


class TestAdd:
    def test_add_to_backlog(self, meta_repo):
        cmd_todo_add(meta_repo, "New task")
        assert _task_in_section(meta_repo, "New task", "backlog")

    def test_add_with_special_chars(self, meta_repo):
        cases = [
            "Task (with parens)",
            "Task [with brackets]",
            "Task with 'quotes'",
            "Task with & ampersand",
            "Task with $ cash",
            "Async/await pattern",
        ]
        for task in cases:
            cmd_todo_add(meta_repo, task)
            assert _task_in_section(meta_repo, task, "backlog")

    def test_add_multiple(self, meta_repo):
        for i in range(10):
            cmd_todo_add(meta_repo, f"Task {i}")
        content = read_file(meta_repo / "TODO.md")
        pending_count = content.count("- [ ] **")
        assert pending_count == 13  # 10 new + 3 from fixture (2 backlog + 1 blocked)


class TestDone:
    def test_done_moves_to_done(self, meta_repo):
        cmd_todo_done(meta_repo, "Example task one")
        assert _task_in_section(meta_repo, "Example task one", "done")
        assert not _task_in_section(meta_repo, "Example task one", "backlog")

    def test_done_is_idempotent(self, meta_repo):
        cmd_todo_done(meta_repo, "Example task one")
        cmd_todo_done(meta_repo, "Example task one")  # should not crash
        assert _task_in_section(meta_repo, "Example task one", "done")


class TestStart:
    def test_start_moves_to_in_progress(self, meta_repo):
        cmd_todo_start(meta_repo, "Example task one")
        assert _task_in_section(meta_repo, "Example task one", "in-progress")
        assert not _task_in_section(meta_repo, "Example task one", "backlog")

    def test_start_unknown_task(self, meta_repo):
        with pytest.raises(SystemExit):
            cmd_todo_start(meta_repo, "Does not exist")


class TestBlock:
    def test_block_moves_to_blocked(self, meta_repo):
        cmd_todo_block(meta_repo, "Example task one")
        assert _task_in_section(meta_repo, "Example task one", "blocked")

    def test_block_already_blocked(self, meta_repo):
        cmd_todo_block(meta_repo, "Example blocked task")  # already blocked
        assert _task_in_section(meta_repo, "Example blocked task", "blocked")


class TestUnblock:
    def test_unblock_moves_to_backlog(self, meta_repo):
        cmd_todo_unblock(meta_repo, "Example blocked task")
        assert _task_in_section(meta_repo, "Example blocked task", "backlog")

    def test_unblock_normal_task(self, meta_repo):
        cmd_todo_unblock(meta_repo, "Example task one")
        assert _task_in_section(meta_repo, "Example task one", "backlog")


class TestMove:
    def test_move_between_sections(self, meta_repo):
        cmd_todo_move(meta_repo, "Example task one", "next")
        assert _task_in_section(meta_repo, "Example task one", "next")

    def test_move_invalid_target(self, meta_repo):
        with pytest.raises(SystemExit):
            cmd_todo_move(meta_repo, "Example task one", "invalid")

    def test_move_preserves_note(self, meta_repo):
        cmd_todo_note(meta_repo, "Example task one", "note text")
        cmd_todo_move(meta_repo, "Example task one", "next")

        from meta import _parse_todo_sections
        sections = _parse_todo_sections(meta_repo)
        notes = [n for t, n in sections.get("next", []) if t == "Example task one"]
        assert "note text" in notes


class TestBump:
    def test_bump_to_top(self, meta_repo):
        cmd_todo_add(meta_repo, "Bottom task")
        cmd_todo_add(meta_repo, "Top task")
        cmd_todo_bump(meta_repo, "Bottom task")

        content = read_file(meta_repo / "TODO.md")
        # After bump, Bottom should appear before Top in the Backlog section
        backlog_header = SECTION_HEADERS["backlog"]
        backlog_start = content.index(backlog_header)
        backlog_content = content[backlog_start:]
        top_idx = backlog_content.index("**Top task**")
        bottom_idx = backlog_content.index("**Bottom task**")
        assert bottom_idx < top_idx, "Bottom task should be above Top task after bump"


class TestRm:
    def test_rm_removes_task(self, meta_repo):
        cmd_todo_rm(meta_repo, "Example task one")
        assert not _task_in_section(meta_repo, "Example task one", "backlog")

    def test_rm_unknown_task(self, meta_repo):
        with pytest.raises(SystemExit):
            cmd_todo_rm(meta_repo, "Does not exist")

    def test_rm_with_special_chars(self, meta_repo):
        from meta import cmd_todo_add, cmd_todo_rm
        cmd_todo_add(meta_repo, "Task (with parens)")
        cmd_todo_add(meta_repo, "Task [with brackets]")
        cmd_todo_add(meta_repo, "Async/await pattern")
        # These should not raise
        cmd_todo_rm(meta_repo, "Task (with parens)")
        cmd_todo_rm(meta_repo, "Task [with brackets]")
        cmd_todo_rm(meta_repo, "Async/await pattern")
        assert not _task_in_section(meta_repo, "Task (with parens)", "backlog")


class TestLs:
    def test_ls_output(self, meta_repo, capsys):
        cmd_todo_ls(meta_repo)
        captured = capsys.readouterr().out
        assert "Example task one" in captured
        assert "Example task two" in captured
        assert "Example blocked task" in captured

    def test_ls_no_pending(self, meta_repo, capsys):
        cmd_todo_rm(meta_repo, "Example task one")
        cmd_todo_rm(meta_repo, "Example task two")
        cmd_todo_rm(meta_repo, "Example blocked task")
        cmd_todo_ls(meta_repo)
        captured = capsys.readouterr().out
        assert "No pending tasks" in captured


class TestNotes:
    def test_note_add(self, meta_repo):
        cmd_todo_note(meta_repo, "Example task one", "my note")
        assert _task_in_section(meta_repo, "Example task one", "backlog")

    def test_note_update(self, meta_repo):
        cmd_todo_note(meta_repo, "Example task one", "first note")
        cmd_todo_note(meta_repo, "Example task one", "updated note")
        captured = capsys = None  # need output capture
        # Verify via notes command
        from meta import cmd_todo_notes
        # Can't easily capture here, read file directly
        content = read_file(meta_repo / "TODO.md")
        assert "updated note" in content
        assert "first note" not in content

    def test_notes_display(self, meta_repo, capsys):
        cmd_todo_note(meta_repo, "Example task one", "stored note")
        cmd_todo_notes(meta_repo, "Example task one")
        captured = capsys.readouterr().out
        assert "stored note" in captured

    def test_notes_no_note(self, meta_repo, capsys):
        cmd_todo_notes(meta_repo, "Example task one")
        captured = capsys.readouterr().out
        assert "(no note)" in captured

    def test_note_on_done_task(self, meta_repo):
        cmd_todo_done(meta_repo, "Example task one")
        cmd_todo_note(meta_repo, "Example task one", "done note")
        notes_output = None
        content = read_file(meta_repo / "TODO.md")
        assert "done note" in content

    def test_note_roundtrip_after_move(self, meta_repo):
        """Note should survive a section move."""
        cmd_todo_note(meta_repo, "Example task one", "surviving note")
        cmd_todo_move(meta_repo, "Example task one", "next")
        from meta import _parse_todo_sections
        sections = _parse_todo_sections(meta_repo)
        notes = [n for t, n in sections.get("next", []) if t == "Example task one"]
        assert "surviving note" in notes


class TestPrune:
    def test_prune_moves_done_to_archived(self, meta_repo):
        cmd_todo_done(meta_repo, "Example task one")
        cmd_todo_done(meta_repo, "Example task two")
        cmd_todo_prune(meta_repo)

        assert not _task_in_section(meta_repo, "Example task one", "done")
        assert _task_in_section(meta_repo, "Example task one", "archived")

    def test_prune_no_done(self, meta_repo, capsys):
        cmd_todo_prune(meta_repo)
        captured = capsys.readouterr().out
        assert "No completed tasks" in captured

    def test_prune_creates_archived_section(self, meta_repo):
        """Prune should add Archived section if missing."""
        # Remove the Archived section entirely
        content = read_file(meta_repo / "TODO.md")
        content = content.replace(SECTION_HEADERS["archived"], "")
        from meta import write_file
        write_file(meta_repo / "TODO.md", content)

        cmd_todo_done(meta_repo, "Example task one")
        cmd_todo_prune(meta_repo)  # should not crash
        assert _task_in_section(meta_repo, "Example task one", "archived")
