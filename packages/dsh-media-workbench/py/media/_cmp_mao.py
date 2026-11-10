# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()

print("=== 新入库：毛泽东选集（1-5卷·简体完整版）前 2 块 ===")
bid = q("select id from books where title like '%1-5卷%'")[0][0]
for r in q("select page_from, content from book_chunks where book_id=? order by page_from limit 2", (bid,)):
    print("页%s: %s" % (r[0], (r[1] or "").replace("\n", " ")[:300]))
print()
print("=== 旧的 041毛泽东选集.[第一卷] 前 2 块 ===")
r4 = q("select id from books where title like '%041毛泽东选集%'")
if r4:
    for r in q("select page_from, content from book_chunks where book_id=? order by page_from limit 2", (r4[0][0],)):
        print("页%s: %s" % (r[0], (r[1] or "").replace("\n", " ")[:300]))
print()
print("=== 两者对比 ===")
for name, like in [("合订本", "%1-5卷%"), ("041单卷", "%041毛泽东选集%")]:
    r = q("select id from books where title like ?", (like,))
    if r:
        n = q("select sum(length(content)) from book_chunks where book_id=?", (r[0][0],))[0][0]
        cnt = q("select count(*) from book_chunks where book_id=?", (r[0][0],))[0][0]
        # 抽「矛盾论」出现次数
        rows = q("select content from book_chunks where book_id=?", (r[0][0],))
        txt = "".join(x[0] or "" for x in rows)
        print("  %s: %s 字 %s 块 | 矛盾论 %d 次 | 实践论 %d 次" % (name, n, cnt, txt.count("矛盾论"), txt.count("实践论")))
