# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
rows = c.execute("""
  select s.id, s.board, s.note, s.text, b.title, b.category, s.created_at
  from split_items s left join books b on b.id = s.post_id
  where s.source='book' and (s.text like '%扭转体式%' or s.text like '%鹰式%')
""").fetchall()
print("两条完整记录：\n")
for i, r in enumerate(rows, 1):
    print("【第 %d 条】" % i)
    print("书名：", r[4], "｜分类：", r[5])
    print("板块：", r[1])
    print("提炼：", r[2])
    print("原文：", r[3])
    print()
print("=== 这个系列一共几本、拆出多少条 ===")
for r in c.execute("""select b.title, count(*) n from split_items s join books b on b.id=s.post_id
                      where b.title like '%脉轮%' or b.title like '%冥想%' or b.title like '%瑜伽%'
                      group by b.id order by n desc limit 8"""):
    print("  %-28s %5d 条" % (r[0][:28], r[1]))
c.close()
