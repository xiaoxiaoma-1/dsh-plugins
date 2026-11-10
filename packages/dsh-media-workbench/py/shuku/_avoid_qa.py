# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
for board, label in (("avoid", "避坑"), ("qa", "问答")):
    print("========== %s ==========" % label)
    rows = c.execute("""
      select s.text, s.note, b.title, b.category
      from split_items s left join books b on b.id = s.post_id
      where s.source='book' and s.board=?
      order by random() limit 10
    """, (board,)).fetchall()
    for i, r in enumerate(rows, 1):
        print("%2d. %s" % (i, (r[0] or "").replace("\n", " ")[:150]))
        print("    《%s》｜%s｜提炼:%s" % ((r[2] or "?")[:24], r[3], (r[1] or "")[:24]))
    print()
c.close()
