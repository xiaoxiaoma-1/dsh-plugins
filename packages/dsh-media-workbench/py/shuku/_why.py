# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
for t in ("江恩", "密钥", "通道冲浪"):
    r = c.execute("select title, category, source_path from books where title like ? limit 1", ("%" + t + "%",)).fetchone()
    if r:
        print("书名:", r[0])
        print("分类:", r[1])
        print("来源路径:", r[2])
        print("---")
c.close()
