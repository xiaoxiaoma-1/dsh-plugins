# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()

for kw in ["一坨面坨", "一坨面头", "面坨"]:
    print("==", kw)
    found = False
    for tb, col in [("posts", "author"), ("posts", "text"), ("live_watch", "label"),
                    ("live_watch", "url"), ("post_sources", "author")]:
        try:
            n = c.execute("select count(*) from %s where %s like ?" % (tb, col), ("%" + kw + "%",)).fetchone()[0]
            if n:
                print("   %s.%s: %d 条" % (tb, col, n))
                found = True
        except Exception:
            pass
    if not found:
        print("   （没有）")

print()
print("=== live_watch 全部 ===")
for r in q("select * from live_watch"):
    print("  ", r)

print()
print("=== 最近的 douyin posts（近 3 天）===")
for r in q("""select id, coalesce(author,''), date, substr(text,1,50)
              from posts where kind='douyin' and created_at >= date('now','-3 day')
              order by created_at desc limit 15"""):
    print("   %s | %-28s | %s | %s" % (r[0][:30], r[1][:28], r[2], (r[3] or "").replace("\n", " ")[:40]))

print()
print("=== posts 里 author 含'面'的 ===")
for r in q("select distinct author from posts where author like '%面%'"):
    print("   ", r[0][:60])
c.close()
