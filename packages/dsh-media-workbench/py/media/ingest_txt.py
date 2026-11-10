# -*- coding: utf-8 -*-
"""把 txt 全文入库成书（切块 + 建索引 + 分类标记）"""
import os, re, sqlite3, sys, time, hashlib
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
CHUNK = 2000


def ingest(txt_path, title, author="", topic="", subs=""):
    raw = open(txt_path, encoding="utf-8").read()
    raw = raw.replace("\r\n", "\n")
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    total = len(raw)
    # 按段落累积到 2000 字左右切块
    paras = [p.strip() for p in raw.split("\n") if p.strip()]
    chunks, buf, head = [], [], ""
    for p in paras:
        if len(p) < 40 and not head and len(p) < 60:
            head = p[:60]
        buf.append(p)
        if sum(len(x) for x in buf) >= CHUNK:
            chunks.append((head, "\n".join(buf)))
            buf, head = [], ""
    if buf:
        chunks.append((head, "\n".join(buf)))

    bid = "book_" + hashlib.md5((title + str(total)).encode("utf-8")).hexdigest()[:12]
    c = sqlite3.connect(DB)
    c.execute("delete from book_chunks where book_id=?", (bid,))
    c.execute("delete from books where id=?", (bid,))
    c.execute("delete from chunks_fts where book_id=?", (bid,))
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    est_pages = max(1, total // 1000)
    c.execute("""insert into books(id,title,author,source_path,pages,ocr_state,quality,summary,doable,category,created_at)
                 values(?,?,?,?,?,?,?,?,?,?,?)""",
              (bid, title, author, txt_path, est_pages, "done", "", "", "", "", now))
    for i, (hd, content) in enumerate(chunks):
        cid = "%s_c%04d" % (bid, i)
        c.execute("insert into book_chunks(id,book_id,page_from,page_to,heading,content,chars,created_at)"
                  " values(?,?,?,?,?,?,?,?)",
                  (cid, bid, int(i * est_pages / max(1, len(chunks))) + 1,
                   int((i + 1) * est_pages / max(1, len(chunks))), hd[:80], content, len(content), now))
        c.execute("insert into chunks_fts(tok, content, book_id, page_from) values(?,?,?,?)",
                  (" ".join(content), content, bid, i + 1))
    if topic:
        c.execute("insert or replace into book_labels values(?,?,?,?,?,?,?)",
                  (bid, topic, "", subs.split(",")[0] if subs else "", subs, 1.0, now))
    c.commit()
    c.close()
    print("入库《%s》| %d 字 | %d 块 | id=%s" % (title, total, len(chunks), bid))
    return bid, total, len(chunks)


if __name__ == "__main__":
    ingest(r"E:\wengao_新书\毛选_2MB.txt", "毛泽东选集（1-5卷·简体完整版）", "毛泽东",
           "权谋与政治", "毛选")
