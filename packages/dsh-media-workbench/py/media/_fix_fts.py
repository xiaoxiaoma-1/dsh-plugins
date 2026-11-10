# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s: c.execute(s).fetchall()
for r in q("select name, sql from sqlite_master where name like 'chunks_fts%'"):
    print(r[0], "::", (r[1] or "")[:300])
print()
print("fts 主表行数", q("select count(*) from chunks_fts")[0][0])
print("fts_data 行数", q("select count(*) from chunks_fts_data")[0][0])
print("fts_docsize 行数", q("select count(*) from chunks_fts_docsize")[0][0])
print("book_chunks 行数", q("select count(*) from book_chunks")[0][0])
print()
print("== 试 rebuild ==")
try:
    c.execute("insert into chunks_fts(chunks_fts) values('rebuild')")
    c.commit()
    print("rebuild 完成")
    print("fts 现在行数", q("select count(*) from chunks_fts")[0][0])
    for kw in ["权力", "王阳明", "知行合一"]:
        print("  match %s -> %d" % (kw, q("select count(*) from chunks_fts where chunks_fts match '%s'" % kw)[0][0]))
except Exception as e:
    print("rebuild 失败:", e)
