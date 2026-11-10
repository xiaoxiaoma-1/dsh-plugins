# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
rows = c.execute("""
  select s.text, s.note, b.title, b.category
  from split_items s join books b on b.id = s.post_id
  where s.source='book' and s.board='quote'
    and length(s.text) between 20 and 90
    and b.category not in ('冥想与身心','身心与养生','待定')
    and s.text not like '%页%'
    and s.text not like '%图%'
  order by random() limit 10
""").fetchall()
for i, r in enumerate(rows, 1):
    print("%d. %s" % (i, r[0].replace("\n", " ")))
    print("   —— 《%s》｜%s" % (r[2][:30], r[3]))
    print("   （提炼：%s）" % r[1])
    print()
c.close()
