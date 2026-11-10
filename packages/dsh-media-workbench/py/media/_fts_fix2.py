# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s: c.execute(s).fetchall()

print("== 短语查询测试 ==")
for expr in ['"权 力"', '"王 阳 明"', '"知 行 合 一"', '"毛 泽 东"']:
    try:
        n = q("select count(*) from chunks_fts where tok match '%s'" % expr)[0][0]
        print("  match %s -> %d" % (expr, n))
    except Exception as e:
        print("  %s 失败 %s" % (expr, e))

print()
print("== rowid 对应关系 ==")
print("  fts rowid=1 的 book_id:", q("select book_id, page_from from chunks_fts where rowid=1"))
print("  book_chunks id=1:", q("select book_id, page_from from book_chunks where id=1"))
print("  fts 行数", q("select count(*) from chunks_fts")[0][0], "chunks 行数", q("select count(*) from book_chunks")[0][0])
orph = q("select count(*) from chunks_fts where rowid not in (select id from book_chunks)")[0][0]
print("  fts 孤儿行（rowid 在 chunks 里找不到）:", orph)
missing = q("select count(*) from book_chunks where id not in (select rowid from chunks_fts)")[0][0]
print("  缺索引的块（chunks 有 fts 没有）:", missing)
