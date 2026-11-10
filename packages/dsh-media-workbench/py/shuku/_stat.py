# -*- coding: utf-8 -*-
import sqlite3

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s: c.execute(s).fetchone()[0]
print("书源素材", q("select count(*) from split_items where source='book'"))
print("稿源素材", q("select count(*) from split_items where source!='book'"))
for b, n in c.execute("select board,count(*) from split_items group by board order by 2 desc"):
    print("  %-6s %5d" % (b, n))
print("已处理块", q("select count(*) from book_split_done"))
print("待处理块", q("""select count(*) from book_chunks ch join books b on b.id=ch.book_id
  where ch.id not in (select chunk_id from book_split_done) and length(ch.content)>=120"""))
print("书总数", q("select count(*) from books"))
print("今日产出", q("select count(*) from split_items where date(created_at)=date('now')"))
c.close()
