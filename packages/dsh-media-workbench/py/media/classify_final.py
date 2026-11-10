# -*- coding: utf-8 -*-
"""补跑剩余 6 本 + 标签同义词归并"""
import json, re, sqlite3, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"E:\desktop\media")
sys.stdout.reconfigure(encoding="utf-8")
from classify3 import call  # noqa

DB = r"E:\desktop\media\workbench.db"
OUT = r"E:\desktop\media\_classify3.json"
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()
res = json.load(open(OUT, encoding="utf-8"))

# ===== ① 补跑 =====
bad = [b for b, o in res.items() if not o.get("topics")]
print("仍失败 %d 本" % len(bad))
rows = []
for bid in bad:
    r = q("select title, coalesce(author,'') from books where id=?", (bid,))
    if not r:
        continue
    chs = q("select content from book_chunks where book_id=? order by page_from limit 3", (bid,))
    txt = "\n…\n".join((x[0] or "")[:400] for x in chs)[:1500]
    rows.append((bid, r[0][0], r[0][1], txt))


def run(row):
    return row[0], call(row[1], row[2], row[3])


fixed = 0
with ThreadPoolExecutor(max_workers=3) as ex:
    for bid, o in ex.map(run, rows):
        if o["topics"]:
            res[bid] = o
            fixed += 1
            print("   ✔ 补回：%s" % q("select title from books where id=?", (bid,))[0][0][:40])
print("补回 %d 本" % fixed)

# ===== ② 标签归并 =====
cnt = Counter()
for o in res.values():
    for t in o.get("tags") or []:
        cnt[t] += 1
before = len(cnt)

# 按长度排序，短的高频词优先作为归并目标
vocab = sorted(cnt.items(), key=lambda x: (-x[1], len(x[0])))
canon = {}
for word, n in vocab:
    if word in canon:
        continue
    canon[word] = word
    for other, m in vocab:
        if other == word or other in canon:
            continue
        # other 包含 word 且长度差 <= 3 → 归并到 word（更短更通用）
        if word in other and len(other) - len(word) <= 3:
            canon[other] = word

merged = 0
for o in res.values():
    tags, seen = [], set()
    for t in o.get("tags") or []:
        c2 = canon.get(t, t)
        if c2 not in seen:
            seen.add(c2)
            tags.append(c2)
    if len(tags) != len(o.get("tags") or []):
        merged += 1
    o["tags"] = tags[:6]

after = len({t for o in res.values() for t in o.get("tags") or []})
print("标签词表 %d → %d（归并了 %d 个同义/包含词，%d 本书的标签被合并）" % (before, after, before - after, merged))

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

# ===== ③ 写库 =====
now = "2026-11-07 09:45:00"
c.execute("delete from book_classify")
n = 0
for bid, o in res.items():
    if not o.get("topics"):
        continue
    c.execute("insert or replace into book_classify values(?,?,?,?,?,?)",
              (bid, ",".join(o["topics"]), ",".join(o["subs"]), ",".join(o["tags"]), o.get("why", ""), now))
    c.execute("insert or replace into book_labels values(?,?,?,?,?,?,?)",
              (bid, o["topics"][0], o["topics"][1] if len(o["topics"]) > 1 else "",
               o["subs"][0] if o["subs"] else "", ",".join(o["subs"]), 1.0, now))
    n += 1
c.commit()
print("\n写入 book_classify %d 行" % n)
print("书总数 %d｜未分类 %d" % (
    q("select count(*) from books")[0][0],
    q("select count(*) from books where id not in (select book_id from book_classify)")[0][0]))

print("\n=== 标签归并后 top25 ===")
cnt2 = Counter()
for o in res.values():
    for t in o.get("tags") or []:
        cnt2[t] += 1
print(cnt2.most_common(25))
c.close()
