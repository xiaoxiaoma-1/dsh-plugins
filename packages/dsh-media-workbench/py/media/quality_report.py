# -*- coding: utf-8 -*-
"""全量判定结果：验收 evidence + 出汇总报告"""
import json, random, re, sqlite3, sys
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
c = sqlite3.connect(DB)
res = json.load(open(r"E:\desktop\media\_quality_tier.json", encoding="utf-8"))
o = []

# ---------- 1. 验收 evidence（随机 40 本） ----------
def norm(s):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")

random.seed(20261107)
sample = random.sample(list(res.items()), min(40, len(res)))
hit = miss = 0
bad = []
for bid, r in sample:
    full = norm("".join(x[0] or "" for x in c.execute(
        "select content from book_chunks where book_id=?", (bid,))))
    for e in r.get("ev") or []:
        if norm(e) and norm(e) in full:
            hit += 1
        else:
            miss += 1
            t = c.execute("select title from books where id=?", (bid,)).fetchone()[0]
            bad.append((t[:36], e))
o.append("【验收】随机 40 本，evidence 命中 %d / 查无 %d，命中率 %.1f%%（门槛 95%%）"
         % (hit, miss, 100.0 * hit / max(1, hit + miss)))
for t, e in bad[:8]:
    o.append("   查无：%s ← %s" % (t, e))
o.append("")

# ---------- 2. 三档分布 ----------
ok = {k: v for k, v in res.items() if v.get("tier")}
o.append("【质量三档】共 %d 本" % len(ok))
for t, n in Counter(v["tier"] for v in ok.values()).most_common():
    o.append("   %s：%d 本" % ({"A": "A 有干货", "B": "B 一般参考", "C": "C 没用"}[t], n))
o.append("")
o.append("【按大类的档位分布】")
dom = defaultdict(Counter)
for bid, v in ok.items():
    r = c.execute("select topic from book_labels where book_id=?", (bid,)).fetchone()
    dom[(r[0] if r else "无分类")][v["tier"]] += 1
for d, cnt in sorted(dom.items(), key=lambda x: -sum(x[1].values())):
    o.append("   %-8s A%-4d B%-4d C%-4d" % (d, cnt["A"], cnt["B"], cnt["C"]))
o.append("")

# ---------- 3. C 档明细 ----------
o.append("【C 档 154 本是什么（按字数排序前 40）】")
cs = sorted([(k, v) for k, v in ok.items() if v["tier"] == "C"],
            key=lambda x: -(x[1].get("chars") or 0))
for bid, v in cs[:40]:
    t, a, p = c.execute("select title,coalesce(author,''),coalesce(pages,0) from books where id=?", (bid,)).fetchone()
    o.append("   %s字 %s页｜%s｜%s｜%s" % (v.get("chars"), p, t[:42], v.get("kind"), v.get("why")))
o.append("")

# ---------- 4. 抽坏（intact=false）名单 ----------
o.append("【抽坏 135 本（intact=false），按字数排】")
bs = sorted([(k, v) for k, v in ok.items() if v.get("intact") is False],
            key=lambda x: (x[1].get("chars") or 0))
for bid, v in bs[:50]:
    t, p = c.execute("select title,coalesce(pages,0) from books where id=?", (bid,)).fetchone()
    o.append("   %s字/%s页=%.1f字页｜%s" % (v.get("chars"), p, (v.get("chars") or 0) / p if p else 0, t[:44]))
o.append("")

# ---------- 5. A 档样例 ----------
o.append("【A 档 367 本，分数最高的 25 本】")
aa = sorted([(k, v) for k, v in ok.items() if v["tier"] == "A"],
            key=lambda x: (-(x[1].get("score") or 0), -(x[1].get("chars") or 0)))
for bid, v in aa[:25]:
    t = c.execute("select title from books where id=?", (bid,)).fetchone()[0]
    o.append("   %s分 %s字｜%s" % (v["score"], v.get("chars"), t[:52]))

open(r"E:\desktop\media\_quality_report.txt", "w", encoding="utf-8").write("\n".join(str(x) for x in o))
print("验证: hit=%d miss=%d rate=%.1f%%" % (hit, miss, 100.0 * hit / max(1, hit + miss)))
print("报告已写")
