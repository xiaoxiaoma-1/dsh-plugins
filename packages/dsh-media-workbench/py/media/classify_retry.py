# -*- coding: utf-8 -*-
"""补跑失败的 8 本 + 写 book_labels 兼容 + 抽样验收"""
import json, sqlite3, sys
sys.path.insert(0, r"E:\desktop\media")
sys.stdout.reconfigure(encoding="utf-8")
from classify3 import call, TREE, ALL_SUBS  # noqa
from concurrent.futures import ThreadPoolExecutor
from collections import Counter

DB = r"E:\desktop\media\workbench.db"
OUT = r"E:\desktop\media\_classify3.json"
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()
res = json.load(open(OUT, encoding="utf-8"))

bad = [bid for bid, v in res.items() if not v.get("topics")]
print("失败 %d 本，补跑：" % len(bad))
rows = []
for bid in bad:
    r = q("select title, coalesce(author,'') from books where id=?", (bid,))
    if not r:
        continue
    t, a = r[0]
    chs = q("select content from book_chunks where book_id=? order by page_from limit 5", (bid,))
    rows.append((bid, t, a, "\n…\n".join((x[0] or "")[:520] for x in chs)[:2400]))
    print("   ", t[:50])


def run(row):
    o = call(row[1], row[2], row[3])
    return row[0], o


ok = 0
with ThreadPoolExecutor(max_workers=4) as ex:
    for bid, o in ex.map(run, rows):
        if o["topics"]:
            res[bid] = o
            ok += 1
print("补回 %d 本" % ok)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

# 写库：book_classify + book_labels 兼容
c.execute("delete from book_classify")
now = "2026-11-07 09:40:00"
for bid, o in res.items():
    if not o.get("topics"):
        continue
    c.execute("insert or replace into book_classify values(?,?,?,?,?,?)",
              (bid, ",".join(o["topics"]), ",".join(o["subs"]), ",".join(o["tags"]), o.get("why", ""), now))
    c.execute("insert or replace into book_labels values(?,?,?,?,?,?,?)",
              (bid, o["topics"][0], o["topics"][1] if len(o["topics"]) > 1 else "",
               o["subs"][0] if o["subs"] else "", ",".join(o["subs"]), 1.0, now))
c.commit()

print("\n=== 验收 ===")
print("book_classify 行数", q("select count(*) from book_classify")[0][0])
print("book_labels 行数  ", q("select count(*) from book_labels")[0][0])
print("书总数            ", q("select count(*) from books")[0][0])
print("未分类的书        ", q("select count(*) from books where id not in (select book_id from book_classify)")[0][0])
print()
sub_cnt = Counter()
for bid, o in res.items():
    for s in o.get("subs") or []:
        sub_cnt[s] += 1
print("子类分布（全部 %d 个）:" % len(ALL_SUBS))
for k, v in sub_cnt.most_common():
    print("   %-8s %d 本" % (k, v))
empty = ALL_SUBS - set(sub_cnt)
print("空子类:", empty if empty else "无")
print()
tag_cnt = Counter()
for o in res.values():
    for t in o.get("tags") or []:
        tag_cnt[t] += 1
print("标签 top30:", tag_cnt.most_common(30))
print("标签总数 %d，只出现 1 次的 %d 个" % (len(tag_cnt), sum(1 for v in tag_cnt.values() if v == 1)))
print()
print("=== 抽样 8 本看标签质量 ===")
import random
random.seed(7)
for bid in random.sample([b for b, o in res.items() if o.get("topics")], 8):
    t = q("select title from books where id=?", (bid,))[0][0]
    o = res[bid]
    print("《%s》" % t[:40])
    print("   大类:%s 子类:%s" % ("/".join(o["topics"]), "/".join(o["subs"])))
    print("   标签:%s" % "、".join(o["tags"]))
c.close()
