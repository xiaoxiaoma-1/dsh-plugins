# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
rows = c.execute("""
  select s.text, b.title from split_items s left join books b on b.id=s.post_id
  where s.source='book' and s.board='qa' order by random() limit 10
""").fetchall()
print("=== 现在库里的「问答」10 条（v1 标准，随机）===")
for i, r in enumerate(rows, 1):
    print("%d. %s" % (i, (r[0] or "").replace("\n", " ")[:110]))
    print("    《%s》" % (r[1] or "?")[:26])
print()
print("问答总数:", c.execute("select count(*) from split_items where source='book' and board='qa'").fetchone()[0])
c.close()
