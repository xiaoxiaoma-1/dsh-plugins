# -*- coding: utf-8 -*-
import os, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()

d = r"E:\desktop\media\_condense"
print("--- 去口水产物目录 ---")
if os.path.isdir(d):
    fs = os.listdir(d)
    print("   文件数:", len(fs))
    for f in fs[:8]:
        print("   ", f)
else:
    print("   没有 _condense 目录")

FILLER = ["啊", "对吧", "就是说", "那个", "然后然后", "嗯", "这个这个", "你看"]

print("\n--- 抖音文案（kind=douyin）---")
print("   条数:", q("select count(*) from posts where kind='douyin'")[0][0])
for r in q("select id, text from posts where kind='douyin' limit 3"):
    t = r[1] or ""
    hits = sum(t.count(w) for w in FILLER)
    per_k = hits / max(1, len(t) / 1000)
    print("   %s | %d 字 | 口水词 %d 个（每千字 %.1f）" % (r[0], len(t), hits, per_k))
    print("     " + t.replace("\n", " ")[:110])

print("\n--- 直播（kind=live）---")
for r in q("select id, text from posts where kind='live' limit 3"):
    t = r[1] or ""
    hits = sum(t.count(w) for w in FILLER)
    per_k = hits / max(1, len(t) / 1000)
    print("   %s | %d 字 | 口水词 %d 个（每千字 %.1f）" % (r[0], len(t), hits, per_k))
    print("     " + t.replace("\n", " ")[:110])
