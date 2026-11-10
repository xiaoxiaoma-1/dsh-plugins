# -*- coding: utf-8 -*-
"""批量入库：用 fitz 提取 + 切块 + 写库（周金涛理论大集两册）。"""
import hashlib
import io
import os
import re
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"
SIZE = 1200

import fitz

TARGETS = [
    (r"E:\tools\asr\downloads\周金涛理论大集_1.pdf", "周金涛理论大集_涛录上册", "周金涛", "财富与投资"),
    (r"E:\tools\asr\downloads\周金涛理论大集_2.pdf", "周金涛理论大集_涛录下册", "周金涛", "财富与投资"),
]


def chunk_text(pages, size=SIZE):
    blocks = []
    buf, buf_len, sp, ep = [], 0, None, None
    for pno, t in pages:
        for para in re.split(r'\n\s*\n', t):
            para = para.strip()
            if not para:
                continue
            if sp is None:
                sp = pno
            ep = pno
            buf.append(para)
            buf_len += len(para)
            if buf_len >= size:
                blocks.append(("".join(buf), sp, ep))
                buf, buf_len, sp = [], 0, None
    if buf:
        blocks.append(("".join(buf), sp or 1, ep or 1))
    return blocks


c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

for pdf, name, author, cat in TARGETS:
    print("=" * 60)
    print("处理:", os.path.basename(pdf))
    if not os.path.exists(pdf):
        print("  文件不存在，跳过")
        continue

    doc = fitz.open(pdf)
    pages = []
    for i in range(doc.page_count):
        t = (doc[i].get_text("text") or "").strip()
        if t:
            pages.append((i + 1, t))
    npages = doc.page_count
    doc.close()

    total = sum(len(t) for _, t in pages)
    print("  页数 %d | 有字 %d 页 | %s 字" % (npages, len(pages), format(total, ",")))
    if total < 500:
        print("  文字太少，跳过")
        continue

    blocks = chunk_text(pages)
    print("  切出 %d 块" % len(blocks))

    bid = "bk_" + hashlib.md5(os.path.normcase(os.path.abspath(pdf)).encode("utf-8")).hexdigest()[:14]
    old = c.execute("select count(*) from book_chunks where book_id=?", (bid,)).fetchone()[0]
    if old:
        print("  已存在 %d 块，先清掉" % old)
        c.execute("delete from book_chunks where book_id=?", (bid,))
        c.execute("delete from books where id=?", (bid,))

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "insert into books(id,title,author,source_path,pages,ocr_state,quality,summary,doable,category,created_at)"
        " values(?,?,?,?,?,?,?,?,?,?,?)",
        (bid, name, author, pdf, npages, "done", "", "", "", cat, now))

    for i, (txt, p1, p2) in enumerate(blocks):
        head = txt.strip().split("\n")[0][:60] if txt.strip() else ""
        c.execute(
            "insert into book_chunks(id,book_id,page_from,page_to,heading,content,chars,created_at)"
            " values(?,?,?,?,?,?,?,?)",
            ("%s_c%04d" % (bid, i), bid, p1, p2, head, txt, len(txt), now))
    c.commit()

    chk = c.execute("select count(*), coalesce(sum(chars),0) from book_chunks where book_id=?", (bid,)).fetchone()
    print("  ✓ %s → %d 块 / %s 字" % (bid, chk[0], format(chk[1], ",")))

print("\n" + "=" * 60)
print("书库: %d 本 / %d 块" % (
    c.execute("select count(*) from books").fetchone()[0],
    c.execute("select count(*) from book_chunks").fetchone()[0]))
c.close()
