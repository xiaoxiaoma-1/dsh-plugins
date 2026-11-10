# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
print("=== 冥想/身心 类的书（有内容入库的）===")
rows = c.execute("""
  select b.title, count(ch.id) n, sum(length(ch.content)) ch
  from books b join book_chunks ch on ch.book_id=b.id
  where b.category in ('冥想与身心','身心与养生') group by b.id order by n desc
""").fetchall()
for r in rows:
    print("  %-46s %4d 块  %7d 字" % (r[0][:46], r[1], r[2] or 0))
print("\n共 %d 本" % len(rows))

print("\n=== 抽 3 块看内容类型 ===")
for r in c.execute("""
  select b.title, substr(ch.content,1,180) from book_chunks ch join books b on b.id=ch.book_id
  where b.category in ('冥想与身心','身心与养生') and length(ch.content)>150
  order by random() limit 3
"""):
    print("【%s】" % r[0][:30])
    print(r[1].replace("\n", " "))
    print()
c.close()
