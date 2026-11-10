# -*- coding: utf-8 -*-
"""恢复被误删的中文版《家庭、私有制和国家的起源》
从批1 全库快照里取回 books 行 + book_chunks + book_labels，再补 fts
"""
import sqlite3, sys, time
sys.stdout.reconfigure(encoding="utf-8")
CUR = r"E:\desktop\media\workbench.db"
SNAP = r"E:\desktop\书库盘点\_清理备份_20261107_批1\workbench_before_batch1.db"

s = sqlite3.connect(SNAP)
cur = sqlite3.connect(CUR)
qs = lambda s_, p=(): s.execute(s_, p).fetchall()

# 找出快照里这本书（中文版，11 万字那本）
rows = qs("""select b.id, b.title, b.author, b.pages, b.ocr_state, b.quality, b.summary,
                    b.doable, b.category, b.created_at,
                    (select sum(length(content)) from book_chunks where book_id=b.id) n
             from books b where b.title like '%家庭%私有制%'""")
print("快照里匹配的书：")
for r in rows:
    print("   id=%s n=%s t=%s" % (r[0], r[10], r[1]))
target = [r for r in rows if r[10] and r[10] < 200000]   # 中文版 10.8 万字
if not target:
    print("没找到目标书"); sys.exit(1)
b = target[0]
print("\n恢复:", b[1], b[10], "字")

# 1. books
cur.execute("insert or replace into books(id,title,author,source_path,pages,ocr_state,quality,summary,doable,category,created_at)"
            " values(?,?,?,?,?,?,?,?,?,?,?)",
            (b[0], b[1], b[2], "", b[3], b[4], b[5], b[6], b[7], b[8], b[9]))
# 2. book_chunks
chunks = qs("select id, book_id, page_from, page_to, heading, content, chars, created_at from book_chunks where book_id=?", (b[0],))
for ch in chunks:
    cur.execute("insert or replace into book_chunks(id,book_id,page_from,page_to,heading,content,chars,created_at)"
                " values(?,?,?,?,?,?,?,?)", ch)
# 3. book_labels
for x in qs("select book_id, topic, topic2, sub, subs, conf, created_at from book_labels where book_id=?", (b[0],)):
    cur.execute("insert or replace into book_labels values(?,?,?,?,?,?,?)", x)
# 4. fts
t0 = time.time()
for ch in chunks:
    cid, bid, pf, pto, hd, content, chars, ca = ch
    tok = " ".join(content or "")
    cur.execute("insert into chunks_fts(tok, content, book_id, page_from) values(?,?,?,?)", (tok, content, bid, pf))
cur.commit()
print("恢复 %d 块，补 fts 耗时 %.1f 秒" % (len(chunks), time.time() - t0))

# 核对
print("\n=== 核对 ===")
print("books", qs("select count(*) from books")[0][0] if False else cur.execute("select count(*) from books").fetchone()[0])
print("chunks", cur.execute("select count(*) from book_chunks").fetchone()[0])
print("fts   ", cur.execute("select count(*) from chunks_fts").fetchone()[0])
print("这本书:", cur.execute("select count(*) from book_chunks where book_id=?", (b[0],)).fetchone()[0], "块")
print("检索测试 '家 庭 私 有 制':", cur.execute(
    """select count(*) from chunks_fts where tok match '"家 庭 私 有 制"'""").fetchone()[0], "条")
cur.close(); s.close()
