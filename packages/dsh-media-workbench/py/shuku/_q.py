# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
print("split_items 总数", c.execute("select count(*) from split_items").fetchone()[0])
print("其中书来源", c.execute("select count(*) from split_items where source='book'").fetchone()[0])
print("已处理块", c.execute("select count(*) from book_split_done").fetchone()[0])
print("样例：")
for r in c.execute("select board,note,substr(text,1,46) from split_items where source='book' limit 5"):
    print("  ", r[0], "|", r[1], "|", r[2])
c.close()
