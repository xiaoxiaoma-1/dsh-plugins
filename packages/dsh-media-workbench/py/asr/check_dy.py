# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
con = sqlite3.connect(r"E:\desktop\media\workbench.db")
print("posts 总数:", con.execute("SELECT COUNT(*) FROM posts").fetchone()[0])
rows = con.execute("SELECT id, author, length(text) FROM posts WHERE id LIKE 'dy_%'").fetchall()
print("dy_ 开头:", len(rows))
for r in rows:
    print("  ", r)
try:
    s = con.execute("SELECT COUNT(*) FROM post_sources").fetchone()[0]
    print("post_sources 总数:", s)
except Exception as e:
    print("post_sources 查询失败:", e)
con.close()
