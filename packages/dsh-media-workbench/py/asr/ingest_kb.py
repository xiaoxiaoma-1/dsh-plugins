# -*- coding: utf-8 -*-
"""用 fitz 提取《涛动周期论》（pypdf 抽不出来，fitz 能）并存进书库。"""
import hashlib
import io
import os
import re
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PDF = r"E:\wengao\涛动周期论_周金涛.pdf"
DB = r"E:\desktop\media\workbench.db"
SIZE = 1200

import fitz

doc = fitz.open(PDF)
pages = []
for i in range(doc.page_count):
    t = (doc[i].get_text("text") or "").strip()
    if t:
        pages.append((i + 1, t))
doc.close()

total_chars = sum(len(t) for _, t in pages)
print("页数: %d | 有文字的页: %d | 总字符: %s" % (
    len(pages) and pages[-1][0] or 0, len(pages), format(total_chars, ",")))

if total_chars < 500:
    print("字符太少，放弃")
    sys.exit(1)


def chunk_text(pages, size=SIZE):
    """按页拼，再按长度+段落切块"""
    blocks = []
    buf = []
    buf_len = 0
    start_page = None
    end_page = None
    for pno, t in pages:
        for para in re.split(r'\n\s*\n', t):
            para = para.strip()
            if not para:
                continue
            if start_page is None:
                start_page = pno
            end_page = pno
            buf.append(para)
            buf_len += len(para)
            if buf_len >= size:
                blocks.append(("".join(buf), start_page, end_page))
                buf, buf_len, start_page = [], 0, None
    if buf:
        blocks.append(("".join(buf), start_page or 1, end_page or 1))
    return blocks


blocks = chunk_text(pages)
print("切出 %d 块" % len(blocks))

# 书名
name = "涛动周期论_周金涛"
bid = "bk_" + hashlib.md5(os.path.normcase(os.path.abspath(PDF)).encode("utf-8")).hexdigest()[:14]

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

exist = c.execute("select id from books where id=?", (bid,)).fetchone()
if exist:
    n = c.execute("select count(*) from book_chunks where book_id=?", (bid,)).fetchone()[0]
    print("已存在（%d 块），先删掉旧的重来" % n)
    c.execute("delete from book_chunks where book_id=?", (bid,))
    c.execute("delete from books where id=?", (bid,))

now = time.strftime("%Y-%m-%d %H:%M:%S")
c.execute(
    "insert into books(id,title,author,source_path,pages,ocr_state,quality,summary,doable,category,created_at)"
    " values(?,?,?,?,?,?,?,?,?,?,?)",
    (bid, name, "周金涛", PDF, pages[-1][0] if pages else 0, "done", "", "", "", "财富与投资", now))

n = 0
for i, (txt, p1, p2) in enumerate(blocks):
    cid = "%s_c%04d" % (bid, i)
    head = txt.strip().split("\n")[0][:60] if txt.strip() else ""
    c.execute(
        "insert into book_chunks(id,book_id,page_from,page_to,heading,content,chars,created_at)"
        " values(?,?,?,?,?,?,?,?)",
        (cid, bid, p1, p2, head, txt, len(txt), now))
    n += 1
c.commit()

chk = c.execute("select count(*), coalesce(sum(chars),0) from book_chunks where book_id=?", (bid,)).fetchone()
print("\n入库完成：%s" % bid)
print("  书块 %d 条 / %s 字" % (chk[0], format(chk[1], ",")))
print("  书库总数: %d 本 / %d 块" % (
    c.execute("select count(*) from books").fetchone()[0],
    c.execute("select count(*) from book_chunks").fetchone()[0]))
c.close()
