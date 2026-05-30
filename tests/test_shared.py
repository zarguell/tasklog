"""Tests for shared helper functions."""

from meta import (
    _extract_note,
    _build_task_line,
    _section_insert_point,
    _parse_todo_sections,
    _recent_log_entries,
    SECTION_HEADERS,
)


class TestExtractNote:
    def test_no_note(self):
        line = "- [ ] **My task**"
        clean, note = _extract_note(line)
        assert clean == "- [ ] **My task**"
        assert note == ""

    def test_with_note(self):
        line = "- [ ] **My task** <!-- note: blocked on review -->"
        clean, note = _extract_note(line)
        assert clean == "- [ ] **My task**"
        assert note == "blocked on review"

    def test_done_with_note(self):
        line = "- [x] **Done thing** <!-- note: finished yesterday -->"
        clean, note = _extract_note(line)
        assert clean == "- [x] **Done thing**"
        assert note == "finished yesterday"

    def test_empty_note(self):
        """Empty HTML comment without 'note:' prefix is not our note format."""
        line = "- [ ] **Task** <!---->"
        clean, note = _extract_note(line)
        # Our regex requires 'note:' — <!----> doesn't match
        assert clean == "- [ ] **Task** <!---->"
        assert note == ""

    def test_note_with_extra_spaces(self):
        line = "- [ ] **Task** <!--  note:  some text  -->"
        clean, note = _extract_note(line)
        assert clean == "- [ ] **Task**"
        assert note == "some text"


class TestBuildTaskLine:
    def test_basic(self):
        assert _build_task_line("Task", " ") == "- [ ] **Task**"

    def test_done(self):
        assert _build_task_line("Task", "x") == "- [x] **Task**"

    def test_with_note(self):
        assert _build_task_line("Task", " ", "blocked") == "- [ ] **Task** <!-- note: blocked -->"

    def test_with_note_done(self):
        assert _build_task_line("Task", "x", "finished") == "- [x] **Task** <!-- note: finished -->"

    def test_roundtrip(self):
        """Build then extract should return original parts."""
        line = _build_task_line("Round Trip", " ", "my note here")
        _, note = _extract_note(line)
        assert note == "my note here"

    def test_special_chars(self):
        line = _build_task_line("Task (with) [brackets] & stuff", " ")
        assert "Task (with) [brackets] & stuff" in line


class TestSectionInsertPoint:
    def _make_lines(self, *headers):
        """Build lines from section header names."""
        lines = []
        for h in headers:
            lines.extend([SECTION_HEADERS[h], ""])
        return lines

    def test_into_empty_section(self):
        """Insert into a section with only a blank line after it."""
        lines = self._make_lines("next", "in-progress", "backlog")
        idx, empty = _section_insert_point(lines, SECTION_HEADERS["in-progress"])
        assert empty is True
        assert idx == lines.index(SECTION_HEADERS["in-progress"]) + 2  # after header + blank line

    def test_into_populated_section(self):
        """Insert before the next section header."""
        lines = [
            SECTION_HEADERS["next"],
            "",
            "- [ ] **Task A**",
            SECTION_HEADERS["backlog"],
            "",
        ]
        idx, empty = _section_insert_point(lines, SECTION_HEADERS["next"])
        assert empty is False
        assert idx == 3  # before backlog header

    def test_last_section_with_content(self):
        """Insert at end if last section has content."""
        lines = [
            SECTION_HEADERS["done"],
            "",
            "- [x] **Done**",
        ]
        idx, empty = _section_insert_point(lines, SECTION_HEADERS["done"])
        assert empty is False
        assert idx == 3  # after the task line, at end

    def test_missing_section(self):
        """Return None when section not found."""
        lines = [SECTION_HEADERS["next"], ""]
        idx, empty = _section_insert_point(lines, "## 🚫 Nope")
        assert idx is None


class TestSectionTopInsertPoint:
    def test_empty_section(self):
        """Top insertion into empty section returns position right after header."""
        lines = [SECTION_HEADERS["next"], "", SECTION_HEADERS["backlog"], ""]
        from meta import _section_top_insert_point
        idx, empty = _section_top_insert_point(lines, SECTION_HEADERS["next"])
        assert empty is True
        assert idx == 1  # right after the header line

    def test_populated_section(self):
        """Top insertion into populated section returns position before first task."""
        lines = [
            SECTION_HEADERS["next"],
            "",
            "- [ ] **Existing**",
            SECTION_HEADERS["backlog"],
        ]
        from meta import _section_top_insert_point
        idx, empty = _section_top_insert_point(lines, SECTION_HEADERS["next"])
        assert empty is False
        assert idx == 2  # position of "Existing" — new task goes before it

    def test_missing_section(self):
        from meta import _section_top_insert_point
        idx, empty = _section_top_insert_point([SECTION_HEADERS["next"]], "## Nope")
        assert idx is None


class TestParseTodoSections:
    def test_empty_repo(self, meta_repo):
        sections = _parse_todo_sections(meta_repo)
        assert "backlog" in sections
        assert "next" in sections
        assert "in-progress" in sections
        assert "blocked" in sections
        assert "done" in sections
        assert "archived" in sections

    def test_parses_tasks_with_notes(self, meta_repo):
        from meta import cmd_todo_add, cmd_todo_note
        cmd_todo_add(meta_repo, "My Task")
        cmd_todo_note(meta_repo, "My Task", "important")

        sections = _parse_todo_sections(meta_repo)
        backlog = sections.get("backlog", [])
        titles = [t for t, _ in backlog]
        notes = [n for _, n in backlog]
        assert "My Task" in titles
        assert "important" in notes

    def test_done_tasks_included(self, meta_repo):
        from meta import cmd_todo_add, cmd_todo_done
        cmd_todo_add(meta_repo, "Finish thing")
        cmd_todo_done(meta_repo, "Finish thing")

        sections = _parse_todo_sections(meta_repo)
        done_tasks = [t for t, _ in sections.get("done", [])]
        assert "Finish thing" in done_tasks


class TestRecentLogEntries:
    def test_empty_log(self, meta_repo):
        entries = _recent_log_entries(meta_repo)
        assert entries == []

    def test_with_entries(self, meta_repo):
        from meta import cmd_log_append
        cmd_log_append(["research | foo | test entry"])
        cmd_log_append(["improvement | bar | second entry"])

        entries = _recent_log_entries(meta_repo)
        assert len(entries) == 2
        assert "foo" in entries[0]
        assert "bar" in entries[1]

    def test_limit(self, meta_repo):
        from meta import cmd_log_append
        for i in range(5):
            cmd_log_append([f"action | topic-{i} | entry {i}"])

        all_entries = _recent_log_entries(meta_repo)
        assert len(all_entries) == 5

        limited = _recent_log_entries(meta_repo, limit=2)
        assert len(limited) == 2
        # Most recent entries
        assert "topic-4" in limited[-1]
        assert "topic-3" in limited[0]
