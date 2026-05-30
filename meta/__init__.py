#!/usr/bin/env python3
"""
tasklog — CLI tool for managing a markdown-based project ledger.

Usage:
  tasklog log <entry>                  Append one-liner to log.md
  tasklog log today                    Show today's log entries
  tasklog log search <term>            Search log entries

  tasklog todo add <task>              Add task to backlog
  tasklog todo done <task>             Mark task as done
  tasklog todo start <task>            Move to In Progress
  tasklog todo block <task>            Move to Blocked
  tasklog todo unblock <task>          Move from Blocked to Backlog
  tasklog todo rm <task>               Remove from TODO.md
  tasklog todo ls                      List pending tasks (with section icons)
  tasklog todo move <task> <section>   Move task to another section
  tasklog todo bump <task>             Move to top of its section
  tasklog todo note <task> <note>      Add/update a note on a task
  tasklog todo notes <task>            Show a task's note
  tasklog todo prune                   Archive old completed tasks

  tasklog context create <name>        Create a new context file
  tasklog context list                  List all context files
  tasklog context archive <name>       Archive a context file

  tasklog status [--verbose]           Show summary (compact by default, --verbose for full)
  tasklog session [--verbose]          Context resume blob for AI session start (compact by default, --verbose for full)

Run from inside a repo directory, or set TASKLOG_REPO to point to one.
Install: pip install -e /path/to/tasklog  (makes `tasklog` available globally)
"""

import argparse
import sys
import os
import re
import subprocess
import datetime
import shutil
from pathlib import Path


REPO_ENV_VAR = "TASKLOG_REPO"
DEFAULT_REPO = ""  # No default — user must set TASKLOG_REPO or run from repo dir

SECTIONS = ["next", "in-progress", "backlog", "blocked", "done", "archived"]
SECTION_HEADERS = {
    "next": "## 🔜 Next",
    "in-progress": "## 🚧 In Progress",
    "backlog": "## 📋 Backlog",
    "blocked": "## 🚫 Blocked",
    "done": "## ✅ Done",
    "archived": "## 🗄️ Archived",
}
SECTION_CHECK = {
    "next": " ",
    "in-progress": " ",
    "backlog": " ",
    "blocked": " ",
    "done": "x",
    "archived": "x",
}
SECTION_ICON = {
    "next": "🔜",
    "in-progress": "🚧",
    "backlog": "📋",
    "blocked": "🚫",
    "done": "✅",
    "archived": "🗄️",
}
SECTION_LABEL = {
    "next": "Next",
    "in-progress": "In Progress",
    "backlog": "Backlog",
    "blocked": "Blocked",
    "done": "Done",
    "archived": "Archived",
}


def find_repo() -> Path:
    env = os.environ.get(REPO_ENV_VAR)
    if env:
        return Path(env).resolve()
    p = Path.cwd().resolve()
    for parent in [p] + list(p.parents):
        if (parent / "README.md").exists() and (parent / "TODO.md").exists():
            return parent
    fallback = DEFAULT_REPO
    if fallback:
        p = Path(fallback).expanduser()
        if p.exists():
            return p
    print("Error: Cannot find tasklog repo.", file=sys.stderr)
    print(f"  Set {REPO_ENV_VAR} or run from within the repo directory.", file=sys.stderr)
    sys.exit(1)


def read_file(path: Path) -> str:
    try:
        return path.read_text()
    except FileNotFoundError:
        fail(f"File not found: {path}")
    except PermissionError:
        fail(f"Permission denied: {path}")


def write_file(path: Path, content: str) -> None:
    try:
        path.write_text(content)
    except PermissionError:
        fail(f"Permission denied: {path}")
    except OSError as e:
        fail(f"Failed to write {path}: {e}")


def git_commit(repo: Path, message: str) -> None:
    try:
        subprocess.run(
            ["git", "-C", str(repo), "add", "-A"],
            capture_output=True, check=True,
        )
        result = subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", message],
            capture_output=True, check=False,
        )
        if result.returncode not in (0, 1):  # 1 = nothing to commit
            print(f"Warning: git commit exited {result.returncode}", file=sys.stderr)
            if result.stderr:
                print(f"  {result.stderr.decode().strip()}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode().strip() if e.stderr else ""
        print(f"Warning: git add failed: {stderr}", file=sys.stderr)


def fail(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def _section_insert_point(lines, section_marker):
    """Find (insert_index, is_empty) for a section heading."""
    marker_idx = None
    for i, line in enumerate(lines):
        if line.strip() == section_marker:
            marker_idx = i
            in_section = True
            continue
        if marker_idx is not None and in_section:
            in_section = False
        if marker_idx is not None and not in_section:
            if line.startswith("## ") and line.strip() != section_marker:
                section_lines = [l for l in lines[marker_idx + 1:i] if l.strip()]
                return i, len(section_lines) == 0
            if i == len(lines) - 1:
                section_lines = [l for l in lines[marker_idx + 1:] if l.strip()]
                return i + 1, len(section_lines) == 0
    return None, False


def _section_top_insert_point(lines, section_marker):
    """Find index to insert at the TOP of a section (right after header + blank lines).
    Returns (insert_index, is_empty) or (None, False) if section not found.
    """
    for i, line in enumerate(lines):
        if line.strip() == section_marker:
            # Skip the header, then any blank lines
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines) or lines[j].strip().startswith("## "):
                # Section is empty (nothing but blank lines before next header)
                return i + 1, True
            # Check if content after this point is only blank lines until next header
            section_lines = [l for l in lines[j:] if l.strip()]
            non_header = [l for l in section_lines if not l.startswith("## ")]
            return j, len(non_header) == 0
    return None, False


def _extract_note(line: str) -> tuple[str, str]:
    """Extract HTML comment note from a task line.
    Returns (line_without_note, note_text) or (line, '').
    """
    m = re.search(r'\s*<!--\s*note:\s*(.*?)\s*-->', line)
    if m:
        clean = line[:m.start()] + line[m.end():]
        return clean.rstrip(), m.group(1).strip()
    return line.rstrip(), ''


def _build_task_line(task: str, checkbox: str, note: str = '') -> str:
    """Build a task line, appending note if present."""
    line = f"- [{checkbox}] **{task}**"
    if note:
        line += f" <!-- note: {note} -->"
    return line


# ── log ──────────────────────────────────────────────────────────


def cmd_log_append(entry_parts):
    repo = find_repo()
    entry = " ".join(entry_parts).strip()

    if not entry:
        fail('log entry cannot be empty.\n  Usage: meta log "action | topic | notes"')

    parts = [p.strip() for p in entry.split("|")]
    action = parts[0] if len(parts) >= 1 else ""
    topic = parts[1] if len(parts) >= 2 else ""
    notes = parts[2] if len(parts) >= 3 else ""
    rest = " | ".join(parts[3:]) if len(parts) > 3 else ""

    if not action or not topic:
        fail('log entry must have at least action and topic.\n  Format: "action | topic | optional notes"')

    date = datetime.date.today().isoformat()
    cols = [date, action, topic, notes]
    if rest:
        cols.append(rest)
    line = "| " + " | ".join(cols) + " |\n"

    log_path = repo / "log.md"
    content = read_file(log_path)

    ARCHIVE_MARKER = "## Archive"
    today_header = f"## {date}"
    today_section = f"## {date}\n\n| Date | Action | Topic | Notes |\n|------|--------|-------|-------|\n"

    # Normalize: ensure exactly one Archive marker at the end
    archive_count = content.count(ARCHIVE_MARKER)
    if archive_count > 1:
        # Collapse duplicates: keep first, remove rest
        lines = content.split("\n")
        seen = False
        cleaned = []
        for line in lines:
            if line.strip() == ARCHIVE_MARKER:
                if not seen:
                    seen = True
                    cleaned.append(line)
            else:
                cleaned.append(line)
        content = "\n".join(cleaned)
    elif archive_count == 0:
        content += f"\n\n{ARCHIVE_MARKER}\n"

    # Insert the entry
    if today_header in content:
        # Today section exists — append line after last today entry
        lines = content.split("\n")
        insert_at = None
        in_today = False
        for i, lt in enumerate(lines):
            if lt.strip() == today_header:
                in_today = True
            elif in_today and lt.strip().startswith("## "):
                insert_at = i
                break
        if insert_at is None:
            # Today is last section before Archive
            for i, lt in enumerate(lines):
                if lt.strip() == today_header:
                    # Find Archive marker after today
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip() == ARCHIVE_MARKER:
                            insert_at = j
                            break
                    break
        if insert_at is not None:
            lines.insert(insert_at, line.rstrip())
            content = "\n".join(lines)
        else:
            # Fallback: append before Archive
            content = content.replace(ARCHIVE_MARKER, line.rstrip() + "\n" + ARCHIVE_MARKER)
    else:
        # New today section — insert before Archive
        content = content.replace(ARCHIVE_MARKER, today_section + line + "\n" + ARCHIVE_MARKER)

    write_file(log_path, content)
    git_commit(repo, f"log: {action} | {topic}")
    print(f"Logged: {date} | {action} | {topic}")


def cmd_log_today():
    repo = find_repo()
    today = datetime.date.today().isoformat()
    content = read_file(repo / "log.md")
    count = 0
    for line in content.split("\n"):
        if line.startswith(f"| {today} "):
            print(line.strip())
            count += 1
    if count == 0:
        print("No entries for today.")


def cmd_log_search(term):
    repo = find_repo()
    term_lower = term.lower()
    content = read_file(repo / "log.md")
    count = 0
    for line in content.split("\n"):
        if re.match(r'^\| \d{4}-\d{2}-\d{2} ', line) and term_lower in line.lower():
            print(line.strip())
            count += 1
    if count == 0:
        print(f"No log entries matching: {term}")


# ── todo ─────────────────────────────────────────────────────────


def cmd_todo_ls(repo):
    content = read_file(repo / "TODO.md")
    # Group pending tasks by section
    lines = content.split("\n")
    current_section = None
    section_tasks = {}
    for line in lines:
        for name, header in SECTION_HEADERS.items():
            if line.strip() == header:
                current_section = name
                if name not in section_tasks:
                    section_tasks[name] = []
                break
        else:
            if current_section and re.match(r'^- \[ \] ', line):
                m = re.match(r'- \[ \] \*\*(.+?)\*\*', line)
                if m:
                    section_tasks.setdefault(current_section, []).append(m.group(1))

    total = sum(len(t) for t in section_tasks.values())
    if total == 0:
        print("No pending tasks.")
    else:
        print(f"{total} pending task(s):")
        for name in ["next", "in-progress", "backlog", "blocked"]:
            tasks = section_tasks.get(name, [])
            if tasks:
                icon = SECTION_ICON[name]
                for t in tasks:
                    print(f"  {icon} ☐ {t}")


def cmd_todo_add(repo, task):
    content = read_file(repo / "TODO.md")
    for section_marker in [SECTION_HEADERS["backlog"], SECTION_HEADERS["next"]]:
        if section_marker not in content:
            continue
        lines = content.split("\n")
        insert_at, is_empty = _section_insert_point(lines, section_marker)
        if insert_at is not None:
            task_line = f"- [ ] **{task}**"
            if is_empty:
                lines.insert(insert_at, "")
                lines.insert(insert_at + 1, task_line)
            else:
                lines.insert(insert_at, task_line)
            content = "\n".join(lines)
            break
    write_file(repo / "TODO.md", content)
    git_commit(repo, f"todo: add {task}")
    print(f"Added: {task}")


def cmd_todo_done(repo, task):
    # Move to the Done section — same as move but with a friendlier name
    cmd_todo_move(repo, task, "done", already_done_ok=True)


def cmd_todo_rm(repo, task):
    content = read_file(repo / "TODO.md")
    escaped = re.escape(task)
    new_content = re.sub(rf'^- \[[ x]\] \*\*{escaped}\*\*.*\n?', '', content, count=1, flags=re.MULTILINE)
    if new_content == content:
        fail(f"Task not found: {task}")
    write_file(repo / "TODO.md", new_content)
    git_commit(repo, f"todo: remove {task}")
    print(f"Removed: {task}")

def cmd_todo_start(repo, task):
    cmd_todo_move(repo, task, "in-progress")

def cmd_todo_block(repo, task):
    cmd_todo_move(repo, task, "blocked")

def cmd_todo_unblock(repo, task):
    """Unblock a task: move to backlog."""
    cmd_todo_move(repo, task, "backlog")

def cmd_todo_move(repo, task, target, already_done_ok=False):
    if target not in SECTIONS:
        valid = ", ".join(s for s in SECTIONS if s != "archived")
        fail(f"Invalid section: {target}. Choose: {valid}")

    content = read_file(repo / "TODO.md")
    escaped = re.escape(task)

    # Check if already in target with correct checkbox
    target_check = SECTION_CHECK[target]
    already = re.search(rf'- \[{target_check}\] \*\*{escaped}\*\*', content)
    if already and already_done_ok:
        print(f"Already {target}: {task}")
        return

    # Find the task line and extract any note
    pattern = rf'^- \[[ x]\] \*\*{escaped}\*\*.*\n?'
    m = re.search(pattern, content, re.MULTILINE)
    if not m:
        fail(f"Task not found: {task}")
    old_line = m.group().rstrip("\n")
    _, note = _extract_note(old_line)

    # Remove it
    content = content[:m.start()] + content[m.end():]

    # Insert into target section
    target_header = SECTION_HEADERS[target]
    checkbox = SECTION_CHECK[target]
    lines = content.split("\n")
    insert_at, is_empty = _section_insert_point(lines, target_header)

    if insert_at is None:
        fail(f"Section '{target}' not found in TODO.md")

    task_line = _build_task_line(task, checkbox, note)
    if is_empty:
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, task_line)
    else:
        lines.insert(insert_at, task_line)

    content = "\n".join(lines)
    write_file(repo / "TODO.md", content)
    git_commit(repo, f"todo: move {task} → {target}")
    print(f"Moved: {task} → {target}")


def cmd_todo_bump(repo, task):
    content = read_file(repo / "TODO.md")
    escaped = re.escape(task)

    # Find the task and its section
    pattern = rf'^- \[[ x]\] \*\*{escaped}\*\*.*'
    m = re.search(pattern, content, re.MULTILINE)
    if not m:
        fail(f"Task not found: {task}")

    full_line = m.group()
    checkbox = full_line[3]  # [ ] or [x]
    _, note_bump = _extract_note(full_line)

    # Determine which section it's in by scanning backward from match
    content_before = content[:m.start()]
    section_found = None
    for name in reversed(SECTIONS):
        if SECTION_HEADERS[name] in content_before:
            section_found = name
            break

    if not section_found:
        fail("Task is not in a recognized section")

    # Remove from current position
    content = content[:m.start()] + content[m.end():]
    # Strip extra blank lines from removal
    content = re.sub(r'\n{3,}', '\n\n', content)

    # Insert at top of its section
    target_header = SECTION_HEADERS[section_found]
    lines = content.split("\n")
    insert_at, is_empty = _section_top_insert_point(lines, target_header)

    task_line = _build_task_line(task, checkbox, note_bump)
    if is_empty:
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, task_line)
    else:
        lines.insert(insert_at, task_line)

    content = "\n".join(lines)
    write_file(repo / "TODO.md", content)
    git_commit(repo, f"todo: bump {task}")
    print(f"Bumped: {task}")


def cmd_todo_prune(repo):
    content = read_file(repo / "TODO.md")
    # Find all done task lines (with notes)
    done_matches = list(re.finditer(r'^- \[x\] \*\*(.+?)\*\*(.*)$', content, re.MULTILINE))
    if not done_matches:
        print("No completed tasks to prune.")
        return

    # Extract full lines for the done tasks (preserve notes)
    done_lines = []
    for m in done_matches:
        full_line = m.group().rstrip()
        # Extract note if present
        _, note = _extract_note(full_line)
        task_title = m.group(1)
        done_lines.append((task_title, note))

    archived_marker = "## 🗄️ Archived"

    # Remove all [x] lines from content
    new_content = re.sub(r'^- \[x\] \*\*.+\n?', '', content, flags=re.MULTILINE)
    # Clean up triple blank lines
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)

    # Ensure Archived section exists
    if archived_marker not in new_content:
        # Insert Archived before "## Archive" (from log rules) or at end
        if "## Archive" in new_content:
            new_content = new_content.replace("## Archive", f"{archived_marker}\n\n" + "## Archive")
        else:
            new_content += f"\n\n{archived_marker}\n"

    # Append done tasks to Archived section
    lines = new_content.split("\n")
    # Find the Archived section
    in_archived = False
    insert_at = None
    for i, line in enumerate(lines):
        if line.strip() == archived_marker:
            in_archived = True
            insert_at = i + 1
        elif in_archived and line.strip().startswith("## "):
            break
        elif in_archived:
            insert_at = i + 1  # keep moving forward
    if insert_at is None:
        # Fallback: append at end
        lines.append("")
        insert_at = len(lines)

    # Build archived task lines
    for task_title, note in done_lines:
        task_line = _build_task_line(task_title, "x", note)
        lines.insert(insert_at, task_line)
        insert_at += 1

    new_content = "\n".join(lines)
    # Clean up any triple blanks from insertion
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)

    write_file(repo / "TODO.md", new_content)
    git_commit(repo, f"todo: pruned {len(done_lines)} completed tasks")
    print(f"Pruned {len(done_lines)} completed task(s) to archived.")


def cmd_todo_note(repo, task, note_text):
    """Add or update a note on a task line."""
    content = read_file(repo / "TODO.md")
    escaped = re.escape(task)

    # Find the task line
    pattern = rf'^- \[[ x]\] \*\*{escaped}\*\*.*\n?'
    m = re.search(pattern, content, re.MULTILINE)
    if not m:
        fail(f"Task not found: {task}")

    old_line = m.group().rstrip("\n")
    clean_line, _ = _extract_note(old_line)
    checkbox = clean_line[3]  # [ ] or [x]

    new_line = _build_task_line(task, checkbox, note_text)
    content = content[:m.start()] + new_line + "\n" + content[m.end():]
    write_file(repo / "TODO.md", content)
    git_commit(repo, f"todo: note {task}")
    print(f"Note added: {task}")


def cmd_todo_notes(repo, task):
    """Show a task and its note."""
    content = read_file(repo / "TODO.md")
    escaped = re.escape(task)

    pattern = rf'^- \[[ x]\] \*\*{escaped}\*\*.*'
    m = re.search(pattern, content, re.MULTILINE)
    if not m:
        fail(f"Task not found: {task}")

    _, note = _extract_note(m.group())
    print(f"Task: {task}")
    if note:
        print(f"Note: {note}")
    else:
        print("(no note)")


# ── shared helpers ──────────────────────────────────────────────


def _parse_todo_sections(repo):
    """Parse TODO.md into {section_name: [(task_title, note), ...]}."""
    content = read_file(repo / "TODO.md")
    lines = content.split("\n")
    current = None
    sections = {}
    for line in lines:
        for name, header in SECTION_HEADERS.items():
            if line.strip() == header:
                current = name
                sections.setdefault(name, [])
                break
        if current and re.match(r'^- \[[ x]\] ', line):
            m = re.match(r'- \[[ x]\] \*\*(.+?)\*\*', line)
            if m:
                _, note = _extract_note(line)
                sections.setdefault(current, []).append((m.group(1), note))
    return sections


def _recent_log_entries(repo, limit=0):
    """Return recent log entries (newest first). limit=0 = all."""
    content = read_file(repo / "log.md")
    entries = []
    for line in content.split("\n"):
        if re.match(r'^\| \d{4}-\d{2}-\d{2} ', line):
            entries.append(line.strip())
    if limit:
        return entries[-limit:]
    return entries


# ── context ──────────────────────────────────────────────────────


def cmd_context_list(repo):
    """List all context files."""
    ctx_dir = repo / "context"
    if not ctx_dir.exists():
        print("No context directory.")
        return
    files = sorted(f for f in ctx_dir.iterdir() if f.suffix == ".md" and f.name != "README.md")
    archived = sorted(f for f in (ctx_dir / "_archived").iterdir()) if (ctx_dir / "_archived").exists() else []
    if not files and not archived:
        print("No context files.")
        return
    for f in files:
        print(f"  📄 {f.stem}")
    if archived:
        print(f"  (📦 {len(archived)} archived)")
    print(f"  Total: {len(files)} active, {len(archived)} archived")


def cmd_context_create(repo, name):
    name = name.strip().lower().replace(" ", "-")
    ctx_path = repo / "context" / f"{name}.md"
    if ctx_path.exists():
        print(f"Context file already exists: {ctx_path}")
        return

    today = datetime.date.today().isoformat()
    template = f"""# {name.replace('-', ' ').title()}

**Date:** {today}
**Status:** Draft

## Overview

<!-- One-paragraph summary of the topic -->

## Key Points

<!-- Bullet-list the main facts, decisions, or findings -->

## Status

<!-- Current state: active, stalled, done, archived -->
"""
    ctx_path.parent.mkdir(parents=True, exist_ok=True)
    write_file(ctx_path, template)
    git_commit(repo, f"context: create {name}")
    print(f"Created: {ctx_path}")


def cmd_context_archive(repo, name):
    name = name.strip().lower().replace(" ", "-")
    src = repo / "context" / f"{name}.md"
    if not src.exists():
        fail(f"Context file not found: {src}")

    archive_dir = repo / "context" / "_archived"
    archive_dir.mkdir(parents=True, exist_ok=True)
    dst = archive_dir / f"{name}.md"
    shutil.move(str(src), str(dst))
    git_commit(repo, f"context: archive {name}")
    print(f"Archived: {name} → context/_archived/")


# ── status ───────────────────────────────────────────────────────


def cmd_status(repo, verbose=False):
    """Show summary. Compact by default, verbose for full layout."""
    sections = _parse_todo_sections(repo)
    counts = {n: len(sections.get(n, [])) for n in SECTIONS}
    pending_total = sum(counts.get(n, 0) for n in ["next", "in-progress", "backlog", "blocked"])
    recent = _recent_log_entries(repo, limit=5)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    if verbose:
        print(f"━━━ meta status — {now} ━━━")
        print()
        for name in ["next", "in-progress", "backlog", "blocked"]:
            c = counts.get(name, 0)
            if c:
                print(f"  {SECTION_ICON[name]} {name}: {c}")
        print(f"  ─── {pending_total} total pending")
        print()
        if recent:
            print(f"Recent log ({len(recent)} entries):")
            for entry in recent:
                print(f"  {entry}")
        print()
        return

    # Compact default
    parts = [f"{SECTION_ICON[n]} {counts.get(n, 0)}" for n in ["next", "in-progress", "backlog", "blocked"] if counts.get(n, 0)]
    print(f"status — {' | '.join(parts) if parts else '0 pending'} ({now})")
    in_progress = sections.get("in-progress", [])
    for t, note in in_progress:
        note_str = f" — {note}" if note else ""
        print(f"  🚧 {t}{note_str}")


# ── session ──────────────────────────────────────────────────────


def cmd_session(repo, verbose=False):
    """Print a compact context resume blob for AI session start."""
    sections = _parse_todo_sections(repo)
    recent = _recent_log_entries(repo, limit=3)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    if verbose:
        print("┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"┃  meta session  ·  {now}")
        print("┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        for name in ["next", "in-progress", "backlog", "blocked"]:
            tasks = sections.get(name, [])
            icon = SECTION_ICON[name]
            label = SECTION_LABEL[name]
            if tasks:
                print(f"┃  {icon} {label}")
                for t, note in tasks:
                    note_str = f" — {note}" if note else ""
                    print(f"┃     ☐ {t}{note_str}")
            else:
                print(f"┃  {icon} {label}: —")
        done_count = len(sections.get("done", []))
        print(f"┃  ✅ Done: {done_count}")
        print("┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        if recent:
            print(f"┃  Recent log ({len(recent)} entries, last 3):")
            for entry in recent:
                print(f"┃    {entry}")
        print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return

    # Compact default
    counts = {n: len(sections.get(n, [])) for n in SECTIONS}
    parts = []
    for n in ["next", "in-progress", "backlog", "blocked"]:
        c = counts.get(n, 0)
        if c:
            parts.append(f"{SECTION_ICON[n]} {c}")
    print(f"meta {' | '.join(parts)}")
    in_progress = sections.get("in-progress", [])
    for t, _ in in_progress:
        print(f"  🚧 {t}")


# ── main ─────────────────────────────────────────────────────────


def cli():
    parser = argparse.ArgumentParser(description="tasklog — manage a markdown-based project ledger")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ── log ──
    p_log = sub.add_parser("log", help="Append entry, show today, or search")
    p_log.add_argument("args", nargs="+", help='Entry: "action | topic | notes", "today", or "search <term>"')

    # ── todo ──
    p_todo = sub.add_parser("todo", help="Manage TODO.md")
    p_todo_sub = p_todo.add_subparsers(dest="todo_cmd", required=True)

    p_todo_sub.add_parser("ls", help="List pending tasks")
    p_todo_sub.add_parser("prune", help="Archive completed tasks")

    p = p_todo_sub.add_parser("add", help="Add task to backlog")
    p.add_argument("task", nargs="+", help="Task description")

    p = p_todo_sub.add_parser("done", help="Mark task as done")
    p.add_argument("task", nargs="+", help="Task description")

    p = p_todo_sub.add_parser("rm", help="Remove task from TODO.md")
    p.add_argument("task", nargs="+", help="Task description")

    p = p_todo_sub.add_parser("move", help="Move task to another section")
    p.add_argument("task", nargs="+", help="Task description + target section (next|in-progress|backlog|blocked|done)")

    p = p_todo_sub.add_parser("bump", help="Move task to top of its section")
    p.add_argument("task", nargs="+", help="Task description")

    p = p_todo_sub.add_parser("start", help="Move task to In Progress")
    p.add_argument("task", nargs="+", help="Task description")

    p = p_todo_sub.add_parser("block", help="Move task to Blocked")
    p.add_argument("task", nargs="+", help="Task description")

    p = p_todo_sub.add_parser("unblock", help="Move task from Blocked to Backlog")
    p.add_argument("task", nargs="+", help="Task description")

    p = p_todo_sub.add_parser("note", help="Add or update a note on a task")
    p.add_argument("task", nargs="+", help="Task description + note text (last arg is the note)")

    p = p_todo_sub.add_parser("notes", help="Show a task's note")
    p.add_argument("task", nargs="+", help="Task description")

    # ── context ──
    p_ctx = sub.add_parser("context", help="Manage context files")
    p_ctx_sub = p_ctx.add_subparsers(dest="ctx_cmd", required=True)

    p = p_ctx_sub.add_parser("create", aliases=["new"], help="Create a new context file")
    p.add_argument("name", help="Topic name (kebab-case or spaces)")

    p = p_ctx_sub.add_parser("list", help="List all context files")

    p = p_ctx_sub.add_parser("archive", help="Archive a context file")
    p.add_argument("name", help="Topic name to archive")

    # ── status ──
    p_status = sub.add_parser("status", help="Show summary (pending + recent log)")
    p_status.add_argument("--verbose", "-v", action="store_true", help="Full layout")

    # ── session ──
    p_sesh = sub.add_parser("session", help="Print context resume blob for AI session start")
    p_sesh.add_argument("--verbose", "-v", action="store_true", help="Full box-drawing format")

    args = parser.parse_args()
    repo = find_repo()

    if args.cmd == "log":
        raw = " ".join(args.args)
        raw_lower = raw.lower()
        if raw_lower in ("today", "t"):
            cmd_log_today()
        elif raw_lower.startswith("search ") or raw_lower.startswith("s "):
            _, _, term = raw.partition(" ")
            cmd_log_search(term.strip())
        else:
            # Treat as append entry
            cmd_log_append(args.args)

    elif args.cmd == "todo":
        if args.todo_cmd == "ls":
            cmd_todo_ls(repo)
        elif args.todo_cmd == "prune":
            cmd_todo_prune(repo)
        elif args.todo_cmd == "add":
            cmd_todo_add(repo, " ".join(args.task))
        elif args.todo_cmd == "done":
            cmd_todo_done(repo, " ".join(args.task))
        elif args.todo_cmd == "rm":
            cmd_todo_rm(repo, " ".join(args.task))
        elif args.todo_cmd == "move":
            # Last arg is the section, rest is task name
            if len(args.task) < 2:
                fail('Usage: meta todo move <task> <section>\n  Section: next, backlog, done')
            *task_parts, target = args.task
            cmd_todo_move(repo, " ".join(task_parts), target)
        elif args.todo_cmd == "bump":
            cmd_todo_bump(repo, " ".join(args.task))
        elif args.todo_cmd == "start":
            cmd_todo_start(repo, " ".join(args.task))
        elif args.todo_cmd == "block":
            cmd_todo_block(repo, " ".join(args.task))
        elif args.todo_cmd == "unblock":
            cmd_todo_unblock(repo, " ".join(args.task))
        elif args.todo_cmd == "note":
            if len(args.task) < 2:
                fail('Usage: meta todo note <task> <note text>')
            *task_parts, note_text = args.task
            cmd_todo_note(repo, " ".join(task_parts), note_text)
        elif args.todo_cmd == "notes":
            cmd_todo_notes(repo, " ".join(args.task))

    elif args.cmd == "context":
        if args.ctx_cmd in ("create", "new"):
            cmd_context_create(repo, args.name)
        elif args.ctx_cmd == "list":
            cmd_context_list(repo)
        elif args.ctx_cmd == "archive":
            cmd_context_archive(repo, args.name)

    elif args.cmd == "status":
        cmd_status(repo, verbose=args.verbose)

    elif args.cmd == "session":
        cmd_session(repo, verbose=args.verbose)


if __name__ == "__main__":
    cli()
