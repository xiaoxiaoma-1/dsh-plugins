# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\书库盘点\pilot_v2.db")
print("=== v3 各板块 ===")
for r in c.execute("select board,count(*),round(avg(score),1) from split_items_v3 group by board order by 2 desc"):
    print("  %-6s %4d 条  均分 %.1f" % r)
print("\n=== 带译文的条目数 ===")
print("  ", c.execute("select count(*) from split_items_v3 where translation<>''").fetchone()[0])
for board, label in (("quote","金句"),("qa","问答"),("hook","钩子")):
    rows = c.execute("select score,text,translation,note from split_items_v3 where board=? order by random() limit 10", (board,)).fetchall()
    print("\n===== %s =====" % label)
    for i, r in enumerate(rows, 1):
        print("%d.[%g] %s" % (i, r[0], (r[1] or "").replace("\n", " ")[:90]))
        if r[2]:
            print("     译：%s" % r[2][:80])
c.close()
