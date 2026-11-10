# -*- coding: utf-8 -*-
"""从备份还原被误删的《毛泽东全集》各卷（纯数字书名的书）。"""
import io
import json
import os
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BAKS = [
    r"E:\desktop\media\_deleted_qm_20261108_231956.json",
    r"E:\desktop\media\_deleted_loose_20261108_231800.json",
    r"E:\desktop\media\_deleted_outdated_20261108_230000.json",
]

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
have = {r[0] for r in c.execute("select id from books")}

restored = []
for bak in BAKS:
    if not os.path.exists(bak):
        continue
    try:
        j = json.load(open(bak, encoding="utf-8"))
    except Exception:
        continue
    books = j.get("books") or []
    chunks = j.get("chunks") or []
    cards = j.get("cards") or []
    if not books:
        continue
    print("检查备份: %s（%d 本）" % (os.path.basename(bak), len(books)))
    for b in books:
        bid = b.get("id")
        t = (b.get("title") or "")
        if bid in have:
            continue
        # 只还原「纯数字书名」或「毛泽东全集」这类真被误删的
        is_num = t.strip().isdigit()
        is_mao = "毛泽东全集" in t or "毛澤东全集" in t
        if not (is_num or is_mao):
            continue
        cols = [k for k in b.keys()]
        ph = ",".join("?" for _ in cols)
        c.execute("insert or replace into books(%s) values(%s)" % (",".join(cols), ph),
                  [b[k] for k in cols])
        n = 0
        for ch in chunks:
            if ch.get("book_id") != bid:
                continue
            cc = list(ch.keys())
            c.execute("insert or replace into book_chunks(%s) values(%s)" % (
                ",".join(cc), ",".join("?" for _ in cc)), [ch[k] for k in cc])
            n += 1
        for cd in cards:
            if cd.get("book_id") != bid:
                continue
            ck = list(cd.keys())
            c.execute("insert or replace into book_card(%s) values(%s)" % (
                ",".join(ck), ",".join("?" for _ in ck)), [cd[k] for k in ck])
        restored.append((t, n))
        print("  ✓ 还原《%s》→ %d 块" % (t[:40], n))

c.commit()

# 补书卡（还原的书没有书卡就重新跑）
print("\n已还原 %d 本" % len(restored))
print("书库: %d 本 / %d 块 / %d 卡" % (
    c.execute("select count(*) from books").fetchone()[0],
    c.execute("select count(*) from book_chunks").fetchone()[0],
    c.execute("select count(*) from book_card").fetchone()[0]))

print("\n== 现在库里纯数字书名的还有哪些 ==")
for r in c.execute("select id,title,pages from books where length(trim(title))<=2"):
    print("  「%s」%s页" % (r["title"], r["pages"]))
c.close()
