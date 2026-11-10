# -*- coding: utf-8 -*-
"""灵感池：承接多来源的想法，最后由每日流程整理成可用内容。

来源 source：
  manual  你自己冒出来的想法（随时说一句就能记）
  atom    从 dbskill 原子库里抽的素材
  hot     今日热点里带下来的
  output  你今天做了什么 / 输出了什么

状态 status：new（未用）/ used（已用）/ dropped（不要了）

用法：
  python ideas.py add "灵感内容" --source manual --note "补充说明"
  python ideas.py list [--status new] [--limit 20]
"""
import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime

DB = r"E:\desktop\media\workbench.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
  id          TEXT PRIMARY KEY,
  source      TEXT NOT NULL DEFAULT 'manual',
  content     TEXT NOT NULL,
  note        TEXT,
  tags        TEXT DEFAULT '[]',
  status      TEXT NOT NULL DEFAULT 'new',
  created_at  TEXT NOT NULL,
  used_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);
CREATE INDEX IF NOT EXISTS idx_ideas_created ON ideas(created_at);
"""


def conn():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.commit()
    return con


def cmd_add(args):
    con = conn()
    now = datetime.now().isoformat(timespec="seconds")
    iid = "idea_" + uuid.uuid4().hex[:12]
    con.execute(
        "INSERT INTO ideas (id, source, content, note, tags, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (iid, args.source, args.content.strip(), args.note or "",
         json.dumps(args.tags or [], ensure_ascii=False), "new", now),
    )
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM ideas WHERE status='new'").fetchone()[0]
    con.close()
    print(f"[ok] 已记下（未用共 {n} 条）")


def cmd_list(args):
    con = conn()
    where = "" if args.status == "all" else "WHERE status = ?"
    params = [] if args.status == "all" else [args.status]
    rows = con.execute(
        f"SELECT * FROM ideas {where} ORDER BY created_at DESC LIMIT ?",
        params + [args.limit],
    ).fetchall()
    con.close()
    if not rows:
        print("（空）")
        return
    for r in rows:
        print(f"[{r['created_at'][5:16]}] ({r['source']}/{r['status']}) {r['content'][:70]}")
        if r["note"]:
            print(f"          备注: {r['note'][:60]}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("content")
    a.add_argument("--source", default="manual",
                   choices=["manual", "atom", "hot", "output"])
    a.add_argument("--note", default="")
    a.add_argument("--tags", nargs="*", default=[])
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("list")
    l.add_argument("--status", default="new", choices=["new", "used", "dropped", "all"])
    l.add_argument("--limit", type=int, default=20)
    l.set_defaults(func=cmd_list)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
