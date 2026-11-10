# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
print("=== 非书源(短视频文案)里的问答，共", c.execute("select count(*) from split_items where source<>'book' and board='qa'").fetchone()[0], "条 ===")
rows = c.execute("""
  select s.text, s.source, s.post_id, p.title
  from split_items s left join posts p on p.id = s.post_id
  where s.source<>'book' and s.board='qa' order by random() limit 10
""").fetchall()
for i, r in enumerate(rows, 1):
    print("%d. %s" % (i, (r[0] or "").replace("\n", " ")[:130]))
    print("    [%s] %s" % (r[1], (r[3] or r[2] or "?")[:40]))
print()
print("=== 各来源条数 ===")
for r in c.execute("select source, count(*) from split_items where board='qa' group by source"):
    print("  %-8s %d" % r)
c.close()
