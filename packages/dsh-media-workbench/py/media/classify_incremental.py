# -*- coding: utf-8 -*-
"""增量分类：只处理还没分类的 posts / live_segments"""
import json, os, sqlite3, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"E:\desktop\media")
from classify3 import TREE, ALL_SUBS, TREE_TXT  # noqa
from classify_posts_v3 import SYS, PROMPT, call  # noqa

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()

rows = []
for pid, author, text in q("""select p.id, coalesce(p.author,''), coalesce(p.text,'') from posts p
        where not exists(select 1 from post_classify pc where pc.src_id = 'post:' || p.id)
          and length(coalesce(p.text,'')) > 150"""):
    rows.append(("post:" + str(pid), (author or "抖音")[:20], text))
for sid, author, text in q("""select l.id, coalesce(l.author,''), coalesce(l.text,'') from live_segments l
        where not exists(select 1 from post_classify pc where pc.src_id = 'live:' || l.id)
          and length(coalesce(l.text,'')) > 150"""):
    rows.append(("live:" + str(sid), (author or "")[:16] + "·直播", text))

print("待分类 %d 条" % len(rows))
if not rows:
    print("没有新的待分类内容")
    c.close()
    sys.exit(0)

res = {}
lock = threading.Lock()
n = [0]


def work(r):
    o = call(r[1], r[2])
    with lock:
        n[0] += 1
        if o["topics"]:
            res[r[0]] = o
    return 1


t0 = time.time()
with ThreadPoolExecutor(max_workers=16) as ex:
    list(ex.map(work, rows))
print("分类完成 %d / %d，耗时 %.1f 分" % (len(res), len(rows), (time.time() - t0) / 60))

now = time.strftime("%Y-%m-%d %H:%M:%S")
for k, o in res.items():
    c.execute("insert or replace into post_classify values(?,?,?,?,?,?)",
              (k, ",".join(o["topics"]), ",".join(o["subs"]), ",".join(o["tags"]), o["why"], now))
c.commit()

from collections import Counter
print("大类分布:", Counter(x for o in res.values() for x in o["topics"]).most_common())
for k, o in list(res.items())[:8]:
    t = q("select substr(coalesce(author,''),1,26) from posts where id=?", (k[5:],))
    print("  %s → %s / %s" % ((t[0][0] if t else k)[:26], "/".join(o["topics"]), "/".join(o["subs"])))
print()
print("分类总数:", q("select count(*) from post_classify")[0][0])
c.close()
