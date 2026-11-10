# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
rows = c.execute("""
  select s.board, s.note, s.text, s.post_id, b.title, s.created_at
  from split_items s left join books b on b.id = s.post_id
  where s.source='book' and length(s.text) > 40
  order by s.created_at desc limit 2
""").fetchall()
for i, r in enumerate(rows, 1):
    print("========== 第 %d 条 ==========" % i)
    print("板块：", r[0])
    print("书名：", r[4])
    print("提炼：", r[1])
    print("原文（全）：", r[2])
    print("生成时间：", r[5])
    print()
c.close()
