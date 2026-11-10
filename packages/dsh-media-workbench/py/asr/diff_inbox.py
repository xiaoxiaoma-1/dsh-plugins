# -*- coding: utf-8 -*-
"""对比 ego_inbox.json 里的视频与稿库 posts 表，列出还没转写的。"""
import json
import os
import sqlite3
import sys

DB = r"E:\desktop\media\workbench.db"
INBOX = r"E:\tools\asr\out\ego_inbox.json"

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    inbox = json.load(open(INBOX, encoding="utf-8"))
    items = inbox.get("items") or []
    if not os.path.exists(DB):
        print(json.dumps({"ok": False, "error": "稿库不存在: " + DB}, ensure_ascii=False))
        return
    c = sqlite3.connect(DB)
    cols = [r[1] for r in c.execute("PRAGMA table_info(posts)")]
    print("posts 字段:", ", ".join(cols))
    url_col = "source_url" if "source_url" in cols else ("url" if "url" in cols else None)
    rows = []
    if url_col:
        rows = [r[0] for r in c.execute(f"select {url_col} from posts where {url_col} is not null")]
    blob = "\n".join(str(u) for u in rows)

    todo, done = [], []
    for it in items:
        iid = str(it.get("itemId") or "")
        url = it.get("url") or ""
        hit = (iid and iid in blob) or (url and url in blob)
        (done if hit else todo).append(it)

    total = c.execute("select count(*) from posts").fetchone()[0]
    print(json.dumps({
        "ok": True,
        "posts_total": total,
        "inbox_count": len(items),
        "already": len(done),
        "todo": len(todo),
        "todo_list": [{"itemId": t.get("itemId"), "author": t.get("text"), "url": t.get("url")} for t in todo],
        "done_list": [t.get("text") for t in done],
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
