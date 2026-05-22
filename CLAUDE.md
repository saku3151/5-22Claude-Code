# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
## Running the app

```bash
python3 task_manager.py
```

Or double-click `run.command` in Finder (macOS).

## Architecture

Two-file structure with a strict separation of concerns:

- **`db.py`** — all SQLite access. No UI imports. Exposes plain `dict` results via `sqlite3.Row`.
- **`task_manager.py`** — all Tkinter UI. Calls `db.*` functions; never touches SQLite directly.

### Data model

```
categories  (id, name, color)
tags        (id, name)
tasks       (id, title, description, priority, status, due_date, category_id, created_at, updated_at)
task_tags   (task_id, tag_id)   ← many-to-many join table
```

`PRAGMA foreign_keys = ON` is set on every connection. Deleting a task cascades to `task_tags`; deleting a category sets `tasks.category_id` to NULL.

### Default sort order (db.py `_TASK_ORDER`)

Done tasks sink to the bottom, then sorted by priority (high → medium → low), then by due date ascending (NULL last), then by `created_at DESC`.

### UI flow

`App._refresh()` is the single re-render entry point — called after every mutation. It re-queries `db.get_tasks()` with the current filter state and rebuilds the `ttk.Treeview`.

`_task_map` (dict: treeview iid → task id) bridges the UI widget and the DB row. Always access `self._selected_task_id` through `_on_select`.
