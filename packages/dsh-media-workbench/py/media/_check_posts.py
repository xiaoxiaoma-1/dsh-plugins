# -*- coding: utf-8 -*-
"""查清：库里的书 vs 抖音文案/直播稿，分别有多少、分类情况"""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()

print("=== 各表的真实规模 ===")
for tb in ["books", "book_chunks", "posts", "live_segments", "split_items", "atoms", "ideas",
           "hooks", "book_labels", "post_labels", "book_classify", "live_watch"]:
    try:
        n = q("select count(*) from %s" % tb)[0][0]
        print("   %-16s %d 行" % (tb, n))
    except Exception as e:
        print("   %-16s 不存在/异常 %s" % (tb, str(e)[:30]))

print()
print("=== posts（抖音/口播文案）===")
try:
    cols = [r[1] for r in q("pragma table_info(posts)")]
    print("   字段:", cols)
    print("   条数 %d" % q("select count(*) from posts")[0][0])
    # 找正文字段
    body = "content" if "content" in cols else ("text" if "text" in cols else None)
    if body:
        print("   总字数 %d" % q("select coalesce(sum(length(%s)),0) from posts" % body)[0][0])
    print("   样例 3 条:")
    for r in q("select * from posts limit 3"):
        d = dict(zip(cols, r))
        t = (d.get("title") or d.get("caption") or "")[:30]
        b = (d.get(body) or "")[:80] if body else ""
        print("      %s | %s" % (t, b.replace("\n", " ")))
except Exception as e:
    print("   异常:", e)

print()
print("=== 直播相关 ===")
for tb in ["live_segments", "live_watch"]:
    try:
        cols = [r[1] for r in q("pragma table_info(%s)" % tb)]
        print("   %s 字段: %s" % (tb, cols))
        print("   %s 行数 %d" % (tb, q("select count(*) from %s" % tb)[0][0]))
    except Exception as e:
        print("   %s 异常 %s" % (tb, str(e)[:40]))

print()
print("=== post_labels（文案分类表）===")
try:
    print("   字段:", [r[1] for r in q("pragma table_info(post_labels)")])
    print("   已分类条数:", q("select count(distinct post_id) from post_labels")[0][0] if q("select count(*) from post_labels")[0][0] else 0)
    print("   分类分布:", q("select topic, count(*) from post_labels group by topic order by 2 desc limit 12"))
except Exception as e:
    print("   异常:", e)
c.close()
