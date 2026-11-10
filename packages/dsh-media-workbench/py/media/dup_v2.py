# -*- coding: utf-8 -*-
"""去重 v2：修正分册误判 + 试卷/解析区分，输出精确待删清单"""
import json, re, sqlite3, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s: c.execute(s).fetchall()

books = q("""select b.id, b.title, coalesce(b.author,''), coalesce(b.pages,0),
                    coalesce(x.n,0), coalesce(x.cnt,0)
             from books b left join
             (select book_id, sum(length(content)) n, count(*) cnt from book_chunks group by book_id) x
             on x.book_id=b.id""")

VOL = re.compile(r"(第[一二三四五六七八九十\d]{1,3}[册卷部编集分]|分册|上[册中下]?|下[册中下]?|[上中下]篇)")
KIND = re.compile(r"(试卷|解析|答案|练习|题解|题库|讲义|笔记|导读|评注|注释|全鉴|解读|讲透|品读)")

def norm(t):
    t = t or ""
    t = re.sub(r"[\[\(（【].{0,14}?(精品|完整版|全新|修订|增补|扫描版|高清|pdf|PDF|电子书|txt|插图版|珍藏|版).{0,10}?[\]\)）】]", "", t)
    t = re.sub(r"(全\d+册|全集|全本|完本|修订版|全新修订版|第[一二三四五六七八九十\d]+版|珍藏本|超值白金版|插图版|注音版|扫描版|高清完整版|pdf|PDF|txt|典藏版|精典版)", "", t)
    t = re.sub(r"[《》「」\[\]【】\(\)（）:：，,。．\.、\-_—\s]+", "", t)
    return t.strip()

groups = defaultdict(list)
for bid, t, a, p, n, cnt in books:
    k = norm(t)
    if len(k) < 3:
        continue
    groups[k].append({"id": bid, "title": t, "author": a, "pages": p, "chars": n, "chunks": cnt,
                      "vol": "".join(VOL.findall(t)), "kind": "".join(KIND.findall(t))})

o = ["去重 v2 分析（全库 %d 本）" % len(books), ""]
drop, keep_groups, manual = [], [], []
for k, v in sorted(groups.items(), key=lambda x: -sum(y["chars"] for y in x[1])):
    if len(v) < 2:
        continue
    # 按「册卷标记 + 内容类型标记」再分组：标记不同 = 不是重复
    sub = defaultdict(list)
    for x in v:
        sub[(x["vol"], x["kind"])].append(x)
    for key, items in sub.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda x: -x["chars"])
        top = items[0]
        # 只删字数不超过保留本 1.02 倍的（防止删掉更全的版本）
        todos = [x for x in items[1:] if x["chars"] <= top["chars"] * 1.02]
        bigger = [x for x in items[1:] if x["chars"] > top["chars"] * 1.02]
        o.append("【%s｜册卷=%s｜类型=%s】" % (k[:26], key[0] or "无", key[1] or "无"))
        o.append("   ★保留 %s字 %s块｜%s" % (top["chars"], top["chunks"], top["title"][:48]))
        for x in todos:
            o.append("   ✂ 删  %s字 %s块｜%s" % (x["chars"], x["chunks"], x["title"][:48]))
            drop.append(x)
        for x in bigger:
            o.append("   ⚠ 反了 %s字 比保留本大｜%s" % (x["chars"], x["title"][:48]))
            manual.append(x)
        o.append("")

o.append("=" * 40)
o.append("可删 %d 本，合计 %d 字" % (len(drop), sum(x["chars"] for x in drop)))
json.dump(drop, open(r"E:\desktop\media\_dup_drop.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 分册组（同一套书拆成多册，应合并而非删）
o.append("")
o.append("【分册组：不该删，该合并】")
vols = defaultdict(list)
for k, v in groups.items():
    if len(v) > 1:
        vs = {x["vol"] for x in v if x["vol"]}
        if len(vs) > 1 and len(v) - len(vs) >= 0 and all(x["vol"] for x in v):
            vols[k] = v
for k, v in vols.items():
    o.append("   %s：%d 册 —— %s" % (k[:26], len(v), " / ".join(x["vol"] or "?" for x in v)))

open(r"E:\desktop\media\_dup_v2.txt", "w", encoding="utf-8").write("\n".join(str(x) for x in o))
print("真重复可删 %d 本 %d 字；需人工看 %d 本；分册组 %d 组" % (
    len(drop), sum(x["chars"] for x in drop), len(manual), len(vols)))
