# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"C:\Users\Administrator\.my-memory\memory.db")
print("=== 表 ===")
for r in c.execute("select name from sqlite_master where type='table'"):
    print(" ", r[0])
print("=== memories 结构 ===")
for r in c.execute("PRAGMA table_info(memories)"):
    print("  %-16s %s" % (r[1], r[2]))
print("=== 今天写入的条数 ===")
for r in c.execute("select level, count(*) from memories where date(created_at,'unixepoch','localtime')=date('now','localtime') group by level"):
    print("  ", r)
print("=== 最近的 progress 类 ===")
for r in c.execute("select level,title,substr(content,1,60) from memories order by updated_at desc limit 3"):
    print("  [%s] %s | %s" % (r[0], r[1][:30], r[2]))
c.close()
