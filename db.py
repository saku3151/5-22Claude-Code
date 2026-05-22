import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT NOT NULL UNIQUE,
                color TEXT NOT NULL DEFAULT '#6c757d'
            );

            CREATE TABLE IF NOT EXISTS tags (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                priority    TEXT NOT NULL DEFAULT 'medium'
                                CHECK(priority IN ('high','medium','low')),
                status      TEXT NOT NULL DEFAULT 'todo'
                                CHECK(status IN ('todo','in_progress','done')),
                due_date    TEXT,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS task_tags (
                task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
                PRIMARY KEY (task_id, tag_id)
            );
        """)


# ── categories ──────────────────────────────────────────────────────────────

def get_categories():
    with _connect() as conn:
        return [dict(r) for r in
                conn.execute("SELECT * FROM categories ORDER BY name")]


def add_category(name, color="#6c757d"):
    with _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO categories (name, color) VALUES (?,?)",
                     (name.strip(), color))


def update_category(cat_id, name, color):
    with _connect() as conn:
        conn.execute("UPDATE categories SET name=?, color=? WHERE id=?",
                     (name.strip(), color, cat_id))


def delete_category(cat_id):
    with _connect() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))


# ── tags ────────────────────────────────────────────────────────────────────

def get_tags():
    with _connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM tags ORDER BY name")]


def _get_or_create_tag(conn, name):
    name = name.strip()
    row = conn.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()
    if row:
        return row["id"]
    conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def delete_tag(tag_id):
    with _connect() as conn:
        conn.execute("DELETE FROM tags WHERE id=?", (tag_id,))


# ── tasks ────────────────────────────────────────────────────────────────────

_TASK_SELECT = """
    SELECT t.*,
           c.name  AS category_name,
           c.color AS category_color,
           COALESCE(GROUP_CONCAT(tg.name, ', '), '') AS tags
    FROM tasks t
    LEFT JOIN categories c  ON t.category_id = c.id
    LEFT JOIN task_tags  tt ON t.id = tt.task_id
    LEFT JOIN tags       tg ON tt.tag_id = tg.id
"""

_TASK_ORDER = """
    GROUP BY t.id
    ORDER BY
        CASE t.status WHEN 'done' THEN 1 ELSE 0 END,
        CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
        CASE WHEN t.due_date IS NULL THEN 1 ELSE 0 END,
        t.due_date,
        t.created_at DESC
"""


def get_tasks(status=None, priority=None, category_id=None, search=None):
    where, params = ["1=1"], []
    if status and status != "all":
        where.append("t.status=?"); params.append(status)
    if priority and priority != "all":
        where.append("t.priority=?"); params.append(priority)
    if category_id and category_id != "all":
        where.append("t.category_id=?"); params.append(category_id)
    if search:
        where.append("(t.title LIKE ? OR t.description LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]

    sql = f"{_TASK_SELECT} WHERE {' AND '.join(where)} {_TASK_ORDER}"
    with _connect() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def get_task(task_id):
    sql = f"{_TASK_SELECT} WHERE t.id=? {_TASK_ORDER}"
    with _connect() as conn:
        row = conn.execute(sql, (task_id,)).fetchone()
        return dict(row) if row else None


def add_task(title, description, priority, status, due_date, category_id, tag_names):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title,description,priority,status,due_date,category_id,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (title, description, priority, status, due_date or None, category_id or None, now, now),
        )
        _set_tags(conn, cur.lastrowid, tag_names)
        return cur.lastrowid


def update_task(task_id, title, description, priority, status, due_date, category_id, tag_names):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET title=?,description=?,priority=?,status=?,due_date=?,category_id=?,updated_at=?"
            " WHERE id=?",
            (title, description, priority, status, due_date or None, category_id or None, now, task_id),
        )
        _set_tags(conn, task_id, tag_names)


def delete_task(task_id):
    with _connect() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))


def _set_tags(conn, task_id, tag_names):
    conn.execute("DELETE FROM task_tags WHERE task_id=?", (task_id,))
    for raw in (tag_names or []):
        name = raw.strip()
        if name:
            tid = _get_or_create_tag(conn, name)
            conn.execute("INSERT OR IGNORE INTO task_tags (task_id,tag_id) VALUES (?,?)",
                         (task_id, tid))
