# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
o = []
for title_kw in ["毛泽东全集 第35卷", "马恩全集", "毛泽东全集 第52卷"]:
    r = c.execute("select id,title from books where title like ?", ("%" + title_kw + "%",)).fetchone()
    if not r:
        o.append("找不到 " + title_kw); continue
    rows = c.execute("select page_from, substr(content,1,200) from book_chunks where book_id=? order by page_from", (r[0],)).fetchall()
    o.append("=== %s｜%d 块 ===" % (r[1], len(rows)))
    for i in [len(rows)//10, len(rows)//3, len(rows)//2, len(rows)*3//4, len(rows)-1]:
        if 0 <= i < len(rows):
            o.append("  --- 第%d块 页%s ---" % (i, rows[i][0]))
            o.append("  " + (rows[i][1] or "").replace("\n", " ")[:180])
    o.append("")
open(r"E:\desktop\media\_mao_check.txt", "w", encoding="utf-8").write("\n".join(o))
print("ok")
