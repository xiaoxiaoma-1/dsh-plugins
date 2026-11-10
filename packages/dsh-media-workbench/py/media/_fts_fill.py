# -*- coding: utf-8 -*-
"""给缺失全文索引的书补 fts（tok = 字符间加空格，与现有格式一致）"""
import sqlite3, sys, time
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
c = sqlite3.connect(DB)
q = lambda s: c.execute(s).fetchall()

miss = [r[0] for r in q("select distinct book_id from book_chunks where book_id not in (select distinct book_id from chunks_fts)")]
print("缺索引的书 %d 本" % len(miss))
if miss:
    ph = ",".join("?" * len(miss))
    print("这些书共 %d 块" % q("select count(*) from book_chunks where book_id in (%s)" % ph)[0][0] if False else
          "这些书共 %d 块" % c.execute("select count(*) from book_chunks where book_id in (%s)" % ph, miss).fetchone()[0])
    print("样例书名:", [r[0][:24] for r in c.execute("select title from books where id in (%s) limit 5" % ph, miss)])

    t0 = time.time()
    n = 0
    for bid in miss:
        rows = c.execute("select id, content, page_from from book_chunks where book_id=? order by page_from, id", (bid,)).fetchall()
        for cid, content, pf in rows:
            tok = " ".join(content or "")
            c.execute("insert into chunks_fts(tok, content, book_id, page_from) values(?,?,?,?)",
                      (tok, content, bid, pf))
            n += 1
            if n % 5000 == 0:
                c.commit()
                print("  已补 %d 块 | %.1f 分" % (n, (time.time() - t0) / 60), flush=True)
    c.commit()
    print("补完 %d 块，耗时 %.1f 分" % (n, (time.time() - t0) / 60))

print()
print("=== 最终核对 ===")
print("books %d / chunks %d / fts %d" % (
    q("select count(*) from books")[0][0],
    q("select count(*) from book_chunks")[0][0],
    q("select count(*) from chunks_fts")[0][0]))
print("fts 覆盖书数 %d （应等于 1302）" % q("select count(distinct book_id) from chunks_fts")[0][0])
print("fts 幽灵行 %d （应为 0）" % q("select count(*) from chunks_fts where book_id not in (select id from books)")[0][0])
print("缺索引块 %d （按 book_id+内容核对）" % c.execute(
    """select count(*) from book_chunks bc where not exists(
         select 1 from chunks_fts f where f.book_id=bc.book_id and f.content=bc.content)""").fetchone()[0])
c.close()
