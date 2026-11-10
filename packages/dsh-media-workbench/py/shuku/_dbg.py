# -*- coding: utf-8 -*-
import sqlite3
import sys

sys.path.insert(0, r"E:\desktop\书库盘点")
import extract_split as E

c = sqlite3.connect(E.DB)
row = c.execute(
    "select c.id, b.title, c.content from book_chunks c join books b on b.id=c.book_id "
    "where length(c.content) > 300 limit 1").fetchone()
print("row is None?", row is None)
if row:
    print("书名:", row[1][:30], "块长:", len(row[2]))
    raw = E.call("书名：《%s》\n\n段落：\n%s" % (row[1][:40], row[2][:1200]))
    print("=== 原始返回 ===")
    print((raw or "")[:900])
    print("=== 解析结果 ===")
    print(E.parse(raw))
c.close()
