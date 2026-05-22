#!/usr/bin/env python3
"""Task Manager – Tkinter + SQLite desktop application."""
import tkinter as tk
from tkinter import ttk, messagebox
import re
from datetime import datetime, date

import db

# ── Palette ─────────────────────────────────────────────────────────────────
BG        = "#f5f6fa"
SIDEBAR   = "#2f3542"
HEADER    = "#353b48"
ACCENT    = "#5352ed"
WHITE     = "#ffffff"
TEXT      = "#2f3542"
MUTED     = "#747d8c"
DANGER    = "#ff4757"
SUCCESS   = "#2ed573"
WARNING   = "#ffa502"

PRIORITY_COLOR = {"high": "#ff4757", "medium": "#ffa502", "low": "#2ed573"}
PRIORITY_LABEL = {"high": "高", "medium": "中", "low": "低"}
STATUS_LABEL   = {"todo": "未着手", "in_progress": "進行中", "done": "完了"}
STATUS_COLOR   = {"todo": "#747d8c", "in_progress": "#5352ed", "done": "#2ed573"}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _validate_date(s):
    if not s:
        return True
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))


def _is_overdue(due_date_str):
    if not due_date_str:
        return False
    try:
        return date.fromisoformat(due_date_str) < date.today()
    except ValueError:
        return False


# ── Task Dialog (Add / Edit) ─────────────────────────────────────────────────

class TaskDialog(tk.Toplevel):
    def __init__(self, parent, task=None):
        super().__init__(parent)
        self.result = None
        self.task = task
        self.title("タスクを編集" if task else "タスクを追加")
        self.resizable(False, False)
        self.configure(bg=WHITE)
        self.grab_set()

        self._build()
        if task:
            self._load(task)

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        self.wait_window()

    def _build(self):
        pad = {"padx": 16, "pady": 6}
        f = tk.Frame(self, bg=WHITE)
        f.pack(fill="both", expand=True, padx=24, pady=20)

        def lbl(text):
            tk.Label(f, text=text, bg=WHITE, fg=MUTED, font=("Helvetica", 10)).pack(anchor="w", **pad)

        # Title
        lbl("タイトル *")
        self.title_var = tk.StringVar()
        e = ttk.Entry(f, textvariable=self.title_var, font=("Helvetica", 12), width=42)
        e.pack(fill="x", padx=16, pady=(0, 4))
        e.focus_set()

        # Description
        lbl("説明")
        self.desc_text = tk.Text(f, height=4, font=("Helvetica", 11), relief="solid", bd=1,
                                 wrap="word", fg=TEXT)
        self.desc_text.pack(fill="x", padx=16, pady=(0, 4))

        # Priority & Status (side by side)
        row = tk.Frame(f, bg=WHITE)
        row.pack(fill="x", padx=16, pady=4)

        left = tk.Frame(row, bg=WHITE)
        left.pack(side="left", expand=True, fill="x", padx=(0, 8))
        tk.Label(left, text="優先度", bg=WHITE, fg=MUTED, font=("Helvetica", 10)).pack(anchor="w")
        self.priority_var = tk.StringVar(value="medium")
        for val, lbl_text, color in [("high","高",PRIORITY_COLOR["high"]),
                                      ("medium","中",PRIORITY_COLOR["medium"]),
                                      ("low","低",PRIORITY_COLOR["low"])]:
            tk.Radiobutton(left, text=lbl_text, variable=self.priority_var, value=val,
                           bg=WHITE, fg=color, activebackground=WHITE,
                           selectcolor=WHITE, font=("Helvetica", 11, "bold")).pack(side="left", padx=4)

        right = tk.Frame(row, bg=WHITE)
        right.pack(side="left", expand=True, fill="x")
        tk.Label(right, text="ステータス", bg=WHITE, fg=MUTED, font=("Helvetica", 10)).pack(anchor="w")
        self.status_var = tk.StringVar(value="todo")
        self.status_cb = ttk.Combobox(right, textvariable=self.status_var,
                                       values=["todo", "in_progress", "done"],
                                       state="readonly", width=14)
        self.status_cb.pack(anchor="w")
        # show Japanese labels in combobox display
        self.status_cb["values"] = list(STATUS_LABEL.keys())
        self._status_map = STATUS_LABEL

        # Due date
        lbl("期日 (YYYY-MM-DD)")
        self.due_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.due_var, width=20).pack(anchor="w", padx=16, pady=(0, 4))

        # Category
        lbl("カテゴリ")
        self._cats = db.get_categories()
        cat_names = ["(なし)"] + [c["name"] for c in self._cats]
        self.cat_var = tk.StringVar(value="(なし)")
        ttk.Combobox(f, textvariable=self.cat_var, values=cat_names,
                     state="readonly", width=22).pack(anchor="w", padx=16, pady=(0, 4))

        # Tags
        lbl("タグ (カンマ区切り)")
        self.tags_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.tags_var, width=42).pack(fill="x", padx=16, pady=(0, 4))

        # Buttons
        btn_row = tk.Frame(f, bg=WHITE)
        btn_row.pack(pady=(12, 0))
        tk.Button(btn_row, text="キャンセル", command=self.destroy,
                  bg="#dfe4ea", fg=TEXT, relief="flat", padx=16, pady=8,
                  font=("Helvetica", 11), cursor="hand2").pack(side="left", padx=6)
        tk.Button(btn_row, text="保存", command=self._save,
                  bg=ACCENT, fg=WHITE, relief="flat", padx=24, pady=8,
                  font=("Helvetica", 11, "bold"), cursor="hand2").pack(side="left", padx=6)

    def _load(self, task):
        self.title_var.set(task["title"])
        self.desc_text.insert("1.0", task["description"] or "")
        self.priority_var.set(task["priority"])
        self.status_var.set(task["status"])
        self.due_var.set(task["due_date"] or "")
        if task.get("category_name"):
            self.cat_var.set(task["category_name"])
        if task.get("tags"):
            self.tags_var.set(task["tags"])

    def _save(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("入力エラー", "タイトルは必須です。", parent=self)
            return
        due = self.due_var.get().strip()
        if not _validate_date(due):
            messagebox.showwarning("入力エラー", "期日は YYYY-MM-DD 形式で入力してください。", parent=self)
            return

        cat_name = self.cat_var.get()
        cat_id = None
        if cat_name != "(なし)":
            for c in self._cats:
                if c["name"] == cat_name:
                    cat_id = c["id"]
                    break

        tags = [t.strip() for t in self.tags_var.get().split(",") if t.strip()]
        self.result = dict(
            title=title,
            description=self.desc_text.get("1.0", "end-1c"),
            priority=self.priority_var.get(),
            status=self.status_var.get(),
            due_date=due or None,
            category_id=cat_id,
            tag_names=tags,
        )
        self.destroy()


# ── Category Manager Dialog ───────────────────────────────────────────────────

class CategoryDialog(tk.Toplevel):
    COLORS = ["#ff4757","#ffa502","#2ed573","#5352ed","#1e90ff",
              "#ff6b81","#eccc68","#a29bfe","#00b894","#fd79a8"]

    def __init__(self, parent):
        super().__init__(parent)
        self.title("カテゴリ管理")
        self.resizable(False, False)
        self.configure(bg=WHITE)
        self.grab_set()
        self._build()
        self._refresh()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        self.wait_window()

    def _build(self):
        f = tk.Frame(self, bg=WHITE)
        f.pack(fill="both", expand=True, padx=24, pady=20)

        tk.Label(f, text="カテゴリ一覧", bg=WHITE, fg=TEXT,
                 font=("Helvetica", 13, "bold")).pack(anchor="w", pady=(0, 8))

        self.listbox = tk.Listbox(f, width=32, height=8, font=("Helvetica", 11),
                                  selectmode="single", relief="solid", bd=1)
        self.listbox.pack(fill="x")

        add_f = tk.Frame(f, bg=WHITE)
        add_f.pack(fill="x", pady=(12, 0))

        tk.Label(add_f, text="名前:", bg=WHITE, fg=MUTED, font=("Helvetica", 10)).pack(side="left")
        self.name_var = tk.StringVar()
        ttk.Entry(add_f, textvariable=self.name_var, width=16).pack(side="left", padx=4)

        self.color_var = tk.StringVar(value=self.COLORS[0])
        self._color_btn = tk.Button(add_f, text="  ", bg=self.COLORS[0], relief="solid",
                                    command=self._pick_color, cursor="hand2", bd=1)
        self._color_btn.pack(side="left", padx=4)

        tk.Button(add_f, text="追加", bg=ACCENT, fg=WHITE, relief="flat",
                  font=("Helvetica", 10), padx=10, pady=4, cursor="hand2",
                  command=self._add).pack(side="left", padx=4)

        btn_row = tk.Frame(f, bg=WHITE)
        btn_row.pack(fill="x", pady=(8, 0))
        tk.Button(btn_row, text="削除", bg=DANGER, fg=WHITE, relief="flat",
                  font=("Helvetica", 10), padx=10, pady=4, cursor="hand2",
                  command=self._delete).pack(side="left")
        tk.Button(btn_row, text="閉じる", bg="#dfe4ea", fg=TEXT, relief="flat",
                  font=("Helvetica", 10), padx=10, pady=4, cursor="hand2",
                  command=self.destroy).pack(side="right")

    def _refresh(self):
        self._cats = db.get_categories()
        self.listbox.delete(0, "end")
        for c in self._cats:
            self.listbox.insert("end", c["name"])

    def _pick_color(self):
        idx = self.COLORS.index(self.color_var.get()) if self.color_var.get() in self.COLORS else 0
        idx = (idx + 1) % len(self.COLORS)
        self.color_var.set(self.COLORS[idx])
        self._color_btn.configure(bg=self.COLORS[idx])

    def _add(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("入力エラー", "名前を入力してください。", parent=self)
            return
        db.add_category(name, self.color_var.get())
        self.name_var.set("")
        self._refresh()

    def _delete(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("選択なし", "削除するカテゴリを選択してください。", parent=self)
            return
        cat = self._cats[sel[0]]
        if messagebox.askyesno("確認", f"「{cat['name']}」を削除しますか？\n（タスクのカテゴリは未設定になります）", parent=self):
            db.delete_category(cat["id"])
            self._refresh()


# ── Main Window ───────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        db.init_db()

        self.title("Task Manager")
        self.geometry("1000x640")
        self.minsize(760, 480)
        self.configure(bg=BG)

        self._selected_task_id = None
        self._build_ui()
        self._refresh()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_toolbar()
        self._build_filter_bar()
        self._build_table()
        self._build_statusbar()

    def _build_header(self):
        h = tk.Frame(self, bg=HEADER, height=52)
        h.pack(fill="x")
        h.pack_propagate(False)
        tk.Label(h, text="📋  Task Manager", bg=HEADER, fg=WHITE,
                 font=("Helvetica", 16, "bold")).pack(side="left", padx=20, pady=12)

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=BG, pady=8)
        bar.pack(fill="x", padx=12)

        def btn(parent, text, color, cmd):
            return tk.Button(parent, text=text, bg=color, fg=WHITE, relief="flat",
                             font=("Helvetica", 11), padx=14, pady=6, cursor="hand2",
                             command=cmd, activebackground=color)

        btn(bar, "+ タスク追加", ACCENT, self._add_task).pack(side="left", padx=4)
        btn(bar, "✎ 編集", "#57606f", self._edit_task).pack(side="left", padx=4)
        btn(bar, "✗ 削除", DANGER, self._delete_task).pack(side="left", padx=4)
        tk.Frame(bar, bg=BG, width=20).pack(side="left")
        btn(bar, "カテゴリ管理", "#2f3542", self._manage_categories).pack(side="left", padx=4)

        # quick status toggle
        tk.Frame(bar, bg=BG).pack(side="left", expand=True)
        for status, label in [("todo","未着手"),("in_progress","進行中"),("done","完了")]:
            c = STATUS_COLOR[status]
            tk.Button(bar, text=f"→ {label}", bg=c, fg=WHITE, relief="flat",
                      font=("Helvetica", 10), padx=10, pady=4, cursor="hand2",
                      command=lambda s=status: self._quick_status(s),
                      activebackground=c).pack(side="left", padx=2)

    def _build_filter_bar(self):
        bar = tk.Frame(self, bg="#dfe4ea", pady=6)
        bar.pack(fill="x", padx=0)

        def lbl(text):
            tk.Label(bar, text=text, bg="#dfe4ea", fg=MUTED,
                     font=("Helvetica", 10)).pack(side="left", padx=(12, 2))

        # Search
        lbl("🔍 検索:")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh())
        ttk.Entry(bar, textvariable=self.search_var, width=22,
                  font=("Helvetica", 11)).pack(side="left", padx=4)

        # Status filter
        lbl("ステータス:")
        self.status_filter = tk.StringVar(value="all")
        cb = ttk.Combobox(bar, textvariable=self.status_filter,
                          values=["all","todo","in_progress","done"],
                          state="readonly", width=12)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _: self._refresh())

        # Priority filter
        lbl("優先度:")
        self.priority_filter = tk.StringVar(value="all")
        cb2 = ttk.Combobox(bar, textvariable=self.priority_filter,
                            values=["all","high","medium","low"],
                            state="readonly", width=10)
        cb2.pack(side="left", padx=4)
        cb2.bind("<<ComboboxSelected>>", lambda _: self._refresh())

        # Category filter
        lbl("カテゴリ:")
        self.cat_filter_var = tk.StringVar(value="all")
        self.cat_filter_cb = ttk.Combobox(bar, textvariable=self.cat_filter_var,
                                           state="readonly", width=14)
        self.cat_filter_cb.pack(side="left", padx=4)
        self.cat_filter_cb.bind("<<ComboboxSelected>>", lambda _: self._refresh())

        # Clear filters
        tk.Button(bar, text="✕ クリア", bg="#747d8c", fg=WHITE, relief="flat",
                  font=("Helvetica", 10), padx=8, pady=3, cursor="hand2",
                  command=self._clear_filters).pack(side="left", padx=8)

    def _build_table(self):
        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True, padx=12, pady=(4, 0))

        cols = ("title", "priority", "status", "due_date", "category", "tags")
        self.tree = ttk.Treeview(container, columns=cols, show="headings",
                                 selectmode="browse")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=WHITE, fieldbackground=WHITE,
                        rowheight=32, font=("Helvetica", 11))
        style.configure("Treeview.Heading", background=HEADER, foreground=WHITE,
                        font=("Helvetica", 11, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", "#e8f0fe")],
                  foreground=[("selected", TEXT)])
        style.map("Treeview.Heading", background=[("active", HEADER)])

        headers = {"title":"タイトル","priority":"優先度","status":"ステータス",
                   "due_date":"期日","category":"カテゴリ","tags":"タグ"}
        widths   = {"title":300,"priority":70,"status":90,"due_date":100,
                    "category":110,"tags":200}

        for col in cols:
            self.tree.heading(col, text=headers[col],
                              command=lambda c=col: self._sort(c))
            self.tree.column(col, width=widths[col], minwidth=40,
                             anchor="center" if col != "title" else "w")

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda _: self._edit_task())
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.tag_configure("done",     foreground="#aaa")
        self.tree.tag_configure("overdue",  foreground=DANGER)
        self.tree.tag_configure("high",     font=("Helvetica", 11, "bold"))

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=HEADER, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.status_lbl = tk.Label(bar, text="", bg=HEADER, fg=WHITE,
                                    font=("Helvetica", 9))
        self.status_lbl.pack(side="left", padx=10, pady=4)

    # ── Data / State ─────────────────────────────────────────────────────────

    def _refresh(self):
        self._refresh_cat_filter()

        cat_val = self.cat_filter_var.get()
        cat_id = None
        if cat_val != "all":
            for c in db.get_categories():
                if c["name"] == cat_val:
                    cat_id = c["id"]
                    break

        tasks = db.get_tasks(
            status=self.status_filter.get() if self.status_filter.get() != "all" else None,
            priority=self.priority_filter.get() if self.priority_filter.get() != "all" else None,
            category_id=cat_id,
            search=self.search_var.get().strip() or None,
        )

        self.tree.delete(*self.tree.get_children())
        self._task_map = {}

        for t in tasks:
            due = t["due_date"] or ""
            pri_lbl = PRIORITY_LABEL[t["priority"]]
            sta_lbl = STATUS_LABEL[t["status"]]
            cat = t["category_name"] or ""

            tag = []
            if t["status"] == "done":
                tag.append("done")
            elif _is_overdue(t["due_date"]):
                tag.append("overdue")
            if t["priority"] == "high" and t["status"] != "done":
                tag.append("high")

            iid = self.tree.insert("", "end",
                values=(t["title"], pri_lbl, sta_lbl, due, cat, t["tags"] or ""),
                tags=tag)
            self._task_map[iid] = t["id"]

        total = len(tasks)
        done  = sum(1 for t in tasks if t["status"] == "done")
        self.status_lbl.config(text=f"全 {total} 件  完了 {done} 件")

    def _refresh_cat_filter(self):
        cats = db.get_categories()
        vals = ["all"] + [c["name"] for c in cats]
        self.cat_filter_cb["values"] = vals
        if self.cat_filter_var.get() not in vals:
            self.cat_filter_var.set("all")

    def _clear_filters(self):
        self.search_var.set("")
        self.status_filter.set("all")
        self.priority_filter.set("all")
        self.cat_filter_var.set("all")
        self._refresh()

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        self._selected_task_id = self._task_map.get(sel[0]) if sel else None

    def _sort(self, col):
        rows = [(self.tree.set(iid, col), iid) for iid in self.tree.get_children()]
        rows.sort(key=lambda x: x[0])
        for i, (_, iid) in enumerate(rows):
            self.tree.move(iid, "", i)

    # ── CRUD actions ─────────────────────────────────────────────────────────

    def _add_task(self):
        dlg = TaskDialog(self)
        if dlg.result:
            db.add_task(**dlg.result)
            self._refresh()

    def _edit_task(self):
        if not self._selected_task_id:
            messagebox.showinfo("選択なし", "編集するタスクを選択してください。")
            return
        task = db.get_task(self._selected_task_id)
        dlg = TaskDialog(self, task=task)
        if dlg.result:
            db.update_task(self._selected_task_id, **dlg.result)
            self._refresh()

    def _delete_task(self):
        if not self._selected_task_id:
            messagebox.showinfo("選択なし", "削除するタスクを選択してください。")
            return
        task = db.get_task(self._selected_task_id)
        if messagebox.askyesno("確認", f"「{task['title']}」を削除しますか？"):
            db.delete_task(self._selected_task_id)
            self._selected_task_id = None
            self._refresh()

    def _quick_status(self, new_status):
        if not self._selected_task_id:
            messagebox.showinfo("選択なし", "ステータスを変更するタスクを選択してください。")
            return
        task = db.get_task(self._selected_task_id)
        db.update_task(
            self._selected_task_id,
            title=task["title"],
            description=task["description"] or "",
            priority=task["priority"],
            status=new_status,
            due_date=task["due_date"],
            category_id=task["category_id"],
            tag_names=([t.strip() for t in task["tags"].split(",") if t.strip()]
                       if task.get("tags") else []),
        )
        self._refresh()

    def _manage_categories(self):
        CategoryDialog(self)
        self._refresh()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
