# -*- coding: utf-8 -*-
"""① 删旧毛选（16 繁体分册 + 041 目录膨胀版）② 鬼谷子 4 册合并成一本"""
import hashlib, os, re, sqlite3, sys, time
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BAK = r"E:\desktop\书库盘点\_清理备份_20261107_批4"
os.makedirs(BAK, exist_ok=True)
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()


def delete_books(ids, tag):
    ph = ",".join("?" * len(ids))
    tabs = [r[0] for r in q("select name from sqlite_master where type='table'")
            if any(col[1] == "book_id" for col in c.execute("pragma table_info(%s)" % r[0]))]
    for tb in tabs:
        c.execute("delete from %s where book_id in (%s)" % (tb, ph), ids)
    c.execute("delete from books where id in (%s)" % ph, ids)
    c.commit()
    print("%s：删 %d 本" % (tag, len(ids)))


# ===== ① 旧毛选 =====
old = [r[0] for r in q("""select id from books where (title like '%毛泽东选集%' and title not like '%1-5卷%')
                          or title like '%毛选%' and title like '%分册%'""")]
print("旧毛选 %d 本：%s" % (len(old), [r[0][:40] for r in q("select title from books where id in (%s)" % ",".join("?" * len(old)), old)][:5]))
# 备份正文
import json
exp = {}
for bid in old:
    exp[bid] = [[p, t] for p, t in q("select page_from, content from book_chunks where book_id=?", (bid,))]
json.dump(exp, open(os.path.join(BAK, "旧毛选正文.json"), "w", encoding="utf-8"), ensure_ascii=False)
delete_books(old, "旧毛选")

# ===== ② 鬼谷子 4 册合并 =====
order = ["第一册", "第二册", "第三册", "第四册"]
parts = []
for o in order:
    r = q("select id, title from books where title like ? and title like '%鬼谷子%'", ("%" + o + "%",))
    if r:
        parts.append((o, r[0][0], r[0][1]))
print("\n鬼谷子找到 %d 册：%s" % (len(parts), [p[0] for p in parts]))

if len(parts) >= 2:
    alltxt, chunks = [], []
    for o, bid, t in parts:
        rows = q("select content from book_chunks where book_id=? order by page_from, id", (bid,))
        txt = "\n".join(x[0] or "" for x in rows)
        alltxt.append("【%s】\n%s" % (o, txt))
        chunks.extend([x[0] or "" for x in rows])
    full = "\n\n".join(alltxt)
    total = len(full)
    title = "鬼谷子全集（%d册合并）" % len(parts)
    bid = "book_" + hashlib.md5((title + str(total)).encode()).hexdigest()[:12]
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    c.execute("delete from books where id=?", (bid,))
    c.execute("delete from book_chunks where book_id=?", (bid,))
    c.execute("delete from chunks_fts where book_id=?", (bid,))
    c.execute("""insert into books(id,title,author,source_path,pages,ocr_state,quality,summary,doable,category,created_at)
                 values(?,?,?,?,?,?,?,?,?,?,?)""",
              (bid, title, "鬼谷子", "", total // 1000, "done", "", "", "", "", now))
    # 按原册切块，保留册序信息
    i = 0
    for o, obid, ot in parts:
        rows = q("select content from book_chunks where book_id=? order by page_from, id", (obid,))
        for x in rows:
            content = x[0] or ""
            cid = "%s_c%04d" % (bid, i)
            c.execute("insert into book_chunks(id,book_id,page_from,page_to,heading,content,chars,created_at)"
                      " values(?,?,?,?,?,?,?,?)",
                      (cid, bid, i + 1, i + 1, o, content, len(content), now))
            c.execute("insert into chunks_fts(tok, content, book_id, page_from) values(?,?,?,?)",
                      (" ".join(content), content, bid, i + 1))
            i += 1
    c.execute("insert or replace into book_labels values(?,?,?,?,?,?,?)",
              (bid, "国学与哲学", "", "道家与易", "道家与易", 1.0, now))
    c.commit()
    print("合并入库《%s》%d 字 %d 块 id=%s" % (title, total, i, bid))
    delete_books([p[1] for p in parts], "鬼谷子原分册")

print("\n现库：%d 本 / %d 块 / %d 字" % (
    q("select count(*) from books")[0][0], q("select count(*) from book_chunks")[0][0],
    q("select sum(length(content)) from book_chunks")[0][0]))
c.close()
