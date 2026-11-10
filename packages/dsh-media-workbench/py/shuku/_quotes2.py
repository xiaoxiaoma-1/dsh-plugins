# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
rows = c.execute("""
  select s.text, b.title, b.category
  from split_items s join books b on b.id = s.post_id
  where s.source='book' and s.board='quote'
    and length(s.text) between 18 and 70
    and b.category not in ('冥想与身心','身心与养生','待定','文学与小说')
    and b.title not like '%小说%' and b.title not like '%传奇%' and b.title not like '%将心%'
    and b.title not like '%宋明风云%' and b.title not like '%司马懿%'
    and s.text not like '%“%' and s.text not like '%”%'
  order by random() limit 24
""").fetchall()
for i, r in enumerate(rows, 1):
    print("%2d. %s ｜《%s》" % (i, r[0].replace("\n", " "), r[1][:22]))
c.close()
