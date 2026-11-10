# -*- coding: utf-8 -*-
"""查那 128 本「之前没索引」的书现在是什么、内容怎么样"""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()
rows = q("""select b.id, b.title, coalesce(b.author,''), coalesce(x.n,0), coalesce(x.cnt,0), l.topic
            from books b
            left join (select book_id, sum(length(content)) n, count(*) cnt from book_chunks group by book_id) x on x.book_id=b.id
            left join book_labels l on l.book_id=b.id
            where b.id like 'bk_%'
            order by x.n desc""")
print("bk_ 开头的书 %d 本" % len(rows))
for r in rows[:60]:
    print("  %s字 %s块｜%s｜%s｜%s" % (r[3], r[4], (r[1] or "")[:40], r[2][:12], r[5]))
print()
print("bk_ 书合计字数 %d" % sum(r[3] for r in rows))
