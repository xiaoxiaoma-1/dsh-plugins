# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\书库盘点\pilot_v2.db")
print("=== 各板块产出与分数分布 ===")
for r in c.execute("select board, count(*), round(avg(score),1), min(score), max(score) from split_items_v2 group by board order by 2 desc"):
    print("  %-6s %4d 条  均分 %.1f  (%.0f–%.0f)" % r)
print()
for board, label in (("hook","钩子"),("dry","干货"),("case","案例"),("quote","金句"),("avoid","避坑"),("qa","问答")):
    rows = c.execute("select score, text, note, title from split_items_v2 where board=? order by random() limit 10", (board,)).fetchall()
    print("========== %s（%d 条）==========" % (label, len(rows)))
    for i, r in enumerate(rows, 1):
        print("%d. [%g分] %s" % (i, r[0], (r[1] or "").replace("\n", " ")[:130]))
        print("    《%s》｜%s" % ((r[3] or "?")[:24], (r[2] or "")[:20]))
    print()
c.close()
