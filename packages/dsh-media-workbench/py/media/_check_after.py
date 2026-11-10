# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s: c.execute(s).fetchall()
print("books", q("select count(*) from books")[0][0])
print("chunks", q("select count(*) from book_chunks")[0][0])
print("总字数", q("select sum(length(content)) from book_chunks")[0][0])
for kw in ["权力", "王阳明", "钩子", "毛选"]:
    try:
        n = q("select count(*) from chunks_fts where chunks_fts match '%s'" % kw)[0][0]
        print("FTS '%s' -> %d 条" % (kw, n))
    except Exception as e:
        print("FTS '%s' 异常: %s" % (kw, e))
print("孤儿块", q("select count(*) from book_chunks where book_id not in (select id from books)")[0][0])
print("毛选剩", q("select count(*) from books where title like '%毛泽东选集%'")[0][0])
print("毛选集剩", q("select count(*) from books where title like '%毛选%'")[0][0])
print("毛全集剩", q("select count(*) from books where title like '%毛泽东全集%'")[0][0])
print("分类覆盖", q("select count(distinct book_id) from book_labels")[0][0])
print()
print("== 抽样搜一句原文，验证检索没坏 ==")
r = q("select b.title, substr(f.content,1,80) from chunks_fts f join book_chunks b on b.id=f.rowid where chunks_fts match '知行合一' limit 3")
for x in r:
    print("  ", x[0], "|", x[1].replace("\n", " "))
