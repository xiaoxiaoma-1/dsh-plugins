# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
print("=== 一条真实素材长什么样 ===")
for r in c.execute("select board,note,text from split_items where source='book' and length(text)>40 limit 2"):
    print("板块:", r[0])
    print("提炼:", r[1])
    print("原文:", r[2][:160])
    print("---")
print("=== 素材总数 ===")
print(c.execute("select count(*) from split_items where source='book'").fetchone()[0])
c.close()
