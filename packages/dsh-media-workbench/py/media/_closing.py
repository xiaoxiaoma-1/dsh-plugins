# -*- coding: utf-8 -*-
"""收盘核对"""
import os, sqlite3, sys
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()
print("=== 收盘核对 ===")
for name, sql in [("书", "select count(*) from books"), ("块", "select count(*) from book_chunks"),
                  ("索引", "select count(*) from chunks_fts"), ("字数", "select sum(length(content)) from book_chunks"),
                  ("已分类", "select count(*) from book_classify"),
                  ("未分类", "select count(*) from books where id not in (select book_id from book_classify)"),
                  ("孤儿块", "select count(*) from book_chunks where book_id not in (select id from books)"),
                  ("幽灵索引", "select count(*) from chunks_fts where book_id not in (select id from books)")]:
    print("   %-8s %s" % (name, q(sql)[0][0]))
a = dict(q("select book_id, count(*) from book_chunks group by book_id"))
b = dict(q("select book_id, count(*) from chunks_fts group by book_id"))
print("   块/索引不一致 %d 本" % len({k for k in set(a) | set(b) if a.get(k, 0) != b.get(k, 0)}))
print()
print("=== 分类体系落地情况 ===")
tc = Counter()
sc = Counter()
tgc = Counter()
for tp, ss, tg in q("select topics, subs, tags from book_classify"):
    for x in (tp or "").split(","):
        if x:
            tc[x] += 1
    for x in (ss or "").split(","):
        if x:
            sc[x] += 1
    for x in (tg or "").split(","):
        if x:
            tgc[x] += 1
print("一级大类（可多标签，总数可超书数）:", tc.most_common())
print("二级子类被用到的: %d 个" % len(sc))
print("三级标签词表: %d 个，平均每本 %.1f 个" % (len(tgc), sum(tgc.values()) / 931))
print("标签 top12:", tgc.most_common(12))
print()
print("=== 检索抽样 ===")
for kw in ["权 力", "王 阳 明", "定 价", "毛 泽 东", "习 惯"]:
    print("   '%s' → %d 条" % (kw.replace(" ", ""), q("select count(*) from chunks_fts where tok match '\"%s\"'" % kw)[0][0]))
print()
print("=== 备份残留 ===")
left = []
for base in [r"E:\desktop\书库盘点", r"E:\desktop", "E:\\"]:
    if not os.path.isdir(base):
        continue
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d)
        if os.path.isdir(p) and any(k in d for k in ("备份", "回收", "碎片", "副本")):
            left.append(p)
for p in left:
    print("   ", p)
c.close()
