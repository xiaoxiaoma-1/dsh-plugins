# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
con = sqlite3.connect(r"E:\desktop\media\workbench.db")
con.row_factory = sqlite3.Row

print("=== posts 表 ===")
print("总数:", con.execute("SELECT COUNT(*) FROM posts").fetchone()[0])
r = con.execute("SELECT * FROM posts WHERE id LIKE 'dy_%' ORDER BY created_at DESC LIMIT 1").fetchone()
if r:
    print("最新:", r["id"])
    print("作者/标题:", r["author"])
    print("字数:", len(r["text"]))
    print("正文前 80 字:", r["text"][:80])
    print("原文链接:", r["url"])

print()
print("=== post_sources 表 ===")
s = con.execute("SELECT * FROM post_sources LIMIT 1").fetchone()
if s:
    print(f"平台={s['platform']} 时长={s['duration']:.0f}秒")
    print("标题:", s["title"])
    print("音频:", s["audio_path"])

con.close()
