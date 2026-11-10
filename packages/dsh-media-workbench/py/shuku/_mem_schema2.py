# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"C:\Users\Administrator\.my-memory\memory.db")
for t in ("progress", "project"):
    print("=== %s 结构 ===" % t)
    for r in c.execute("PRAGMA table_info(%s)" % t):
        print("  %-14s %s" % (r[1], r[2]))
print("=== progress 最近 5 条 ===")
for r in c.execute("select * from progress order by rowid desc limit 5"):
    print("  ", r)
print("=== project 今天更新的 ===")
n = c.execute("select count(*) from project where date(updated_at,'unixepoch','localtime')=date('now','localtime')").fetchone()[0]
print("  ", n, "条")
c.close()
