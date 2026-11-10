# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
BASE = """
  from split_items s join books b on b.id = s.post_id
  where s.source='book' and s.board=? and length(s.text) between 25 and 110
    and b.category not in ('冥想与身心','身心与养生','待定','文学与小说')
    and b.title not like '%小说%' and b.title not like '%宋明风云%'
    and s.text not like '%“%'
  order by random() limit 10
"""
for board, label in (("dry", "干货"), ("case", "案例")):
    print("========== %s ==========" % label)
    rows = c.execute("select s.text, s.note, b.title, b.category " + BASE, (board,)).fetchall()
    for i, r in enumerate(rows, 1):
        print("%2d. %s" % (i, r[0].replace("\n", " ")))
        print("    《%s》｜%s" % (r[2][:26], r[3]))
    print()
c.close()
