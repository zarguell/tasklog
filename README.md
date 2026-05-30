# tasklog — Markdown-Based Project Ledger

A CLI tool for managing a lightweight, git-tracked project ledger built from three plain markdown files:

- **`TODO.md`** — what's next (backlog, in-progress, blocked, done)
- **`log.md`** — what happened (append-only chronological changelog)
- **`context/`** — why & how (per-topic research notes and decisions)

No database, no external service, no proprietary format. Just markdown files in a git repo, managed from the terminal.

## Quick Start

```bash
# Install
pip install -e /path/to/tasklog

# Or run without install
python3 -m meta

# Navigate to your repo and start using it
cd my-project
tasklog todo add "Set up CI pipeline"
tasklog start "Set up CI pipeline"
tasklog log "infra | CI | Set up GitHub Actions pipeline"
tasklog status
```

## Usage

### Managing tasks

```bash
tasklog todo add "Task description"      # Add to backlog
tasklog todo start "Task"                 # Move to In Progress
tasklog todo done "Task"                  # Mark done
tasklog todo block "Task"                 # Move to Blocked
tasklog todo unblock "Task"               # Unblock → back to backlog
tasklog todo move "Task" <section>        # Move to any section
tasklog todo bump "Task"                  # Bump to top of its section
tasklog todo rm "Task"                    # Remove from TODO.md
tasklog todo note "Task" "note text"      # Attach a note
tasklog todo notes "Task"                 # Show a task's note
tasklog todo ls                           # List pending tasks
tasklog todo prune                        # Archive completed tasks
```

### Tracking decisions

```bash
tasklog log "action | topic | notes"      # Append one-liner to log.md
tasklog log today                          # Show today's entries
tasklog log search <term>                  # Search the log
```

### Research notes

```bash
tasklog context create "topic"            # Create a new context file
tasklog context list                       # List all context files
tasklog context archive "topic"           # Archive a context file
```

### Reports

```bash
tasklog status                             # Compact summary (default)
tasklog status --verbose                   # Full layout with recent log
tasklog session                            # Compact context resume (for AI handoffs)
tasklog session --verbose                  # Full box-drawing format
```

## Repo Structure

```
your-project/
├── README.md        ← (or AGENTS.md for AI agents)
├── TODO.md          ← backlog & task tracking
├── log.md           ← chronological decision log
└── context/         ← per-topic deep dives
    └── _archived/   ← archived context files
```

## Sections (in TODO.md)

| Section | Status | Checkbox |
|---------|--------|----------|
| `## 🔜 Next` | Next up | `[ ]` |
| `## 🚧 In Progress` | Actively being worked on | `[ ]` |
| `## 📋 Backlog` | General queue | `[ ]` |
| `## 🚫 Blocked` | Waiting on external dependency | `[ ]` |
| `## ✅ Done` | Completed | `[x]` |
| `## 🗄️ Archived` | Pruned from Done | `[x]` |

## Why markdown?

- Version-controlled out of the box (git)
- Editable from any text editor or GitHub web UI
- No lock-in — your data is plain text
- Scriptable — grep, sed, awk all work on the raw files
- AI-friendly — agents can read/write the same format

## Tests

```bash
pip install -e ".[test]"
pytest
```
