# -*- coding: utf-8 -*-
"""清理 chunks_fts 里指向已删书的幽灵行，并核对与 book_chunks 一致"""
import sqlite3, sys, time
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
c = sqlite3.connect(DB)
q = lambda s: c.execute(s).fetchall()

before = q("select count(*) from chunks_fts")[0][0]
ghost = q("select count(*) from chunks_fts where book_id not in (select id from books)")[0][0]
print("清理前 fts %d 行，其中幽灵行 %d" % (before, ghost))

t0 = time.time()
c.execute("delete from chunks_fts where book_id not in (select id from books)")
c.commit()
after = q("select count(*) from chunks_fts")[0][0]
print("清理后 fts %d 行（耗时 %.1f 秒）" % (after, time.time() - t0))

# 反向：chunks 里有但 fts 里没有的（按 book_id+page_from+content 前三字比对成本太高，改按 book_id 抽查）
n_books_chunks = q("select count(distinct book_id) from book_chunks")[0][0]
n_books_fts = q("select count(distinct book_id) from chunks_fts")[0][0]
print("chunks 覆盖书数 %d / fts 覆盖书数 %d" % (n_books_chunks, n_books_fts))
miss = q("select distinct book_id from book_chunks where book_id not in (select distinct book_id from chunks_fts)")[:5]
print("fts 里完全没有的书（前 5 本）:", miss)

print()
print("== 检索功能验证（短语单字法）==")
for kw in ["权 力", "王 阳 明", "钩 子", "毛 泽 东", "知 行 合 一"]:
    n = q("select count(*) from chunks_fts where tok match '\"%s\"'" % kw)[0][0]
    print("  %-10s -> %d 条" % (kw, n))
print()
print("== 用 fts 查一条看能否拿到书名和原文 ==")
r = q("""select b.title, substr(f.content,1,60) from chunks_fts f join books b on b.id=f.book_id
         where f.tok match '"王 阳 明"' limit 3""")
for x in r:
    print("  《%s》 %s" % (x[0][:30], x[1].replace("\n", " ")))
c.close()
