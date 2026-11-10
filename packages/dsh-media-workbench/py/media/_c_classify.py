# -*- coding: utf-8 -*-
"""C 档 154 本分类：小说/文学 · 疑似误判 · 真无用"""
import json, re, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
res = json.load(open(r"E:\desktop\media\_quality_tier.json", encoding="utf-8"))
ok = {k: v for k, v in res.items() if v.get("tier")}

NOVEL = re.compile(r"(小说|叙事|情节|文学|散文|诗歌|诗集|传奇|玄幻|纯爱|言情|穿越|晋江|琅琊榜|上册|下册|第[一二三四五]册|共\d册|三部曲)")
MAO = re.compile(r"(毛泽东|马恩|马克思|恩格斯|列宁|斯大林|选集|文集|全集)")
GARBAGE = re.compile(r"(乱码|符号|无有效|拼凑|跳跃|重复|图片|碎片|不连续|扫描)")

groups = {"① 小说文学（该出库）": [], "② 疑似误判（要人工看）": [], "③ 真无用（可删）": [], "④ 其他": []}
for bid, v in ok.items():
    if v["tier"] != "C":
        continue
    t = c.execute("select title from books where id=?", (bid,)).fetchone()[0]
    why = v.get("why") or ""
    row = (t, v.get("chars") or 0, v.get("kind"), why)
    if MAO.search(t):
        groups["② 疑似误判（要人工看）"].append(row)
    elif NOVEL.search(t + why):
        groups["① 小说文学（该出库）"].append(row)
    elif GARBAGE.search(why):
        groups["③ 真无用（可删）"].append(row)
    else:
        groups["④ 其他"].append(row)

o = ["C 档 154 本分类结果"]
for g, rows in groups.items():
    o.append("")
    o.append("【%s】%d 本" % (g, len(rows)))
    for t, n, k, why in sorted(rows, key=lambda x: -x[1]):
        o.append("   %s字 %s｜%s｜%s" % (n, k, t[:46], why))

# 抽毛选一卷看真实内容
o.append("")
o.append("=" * 30)
o.append("【毛选抽检：第35卷 前 3 块原文】")
r = c.execute("select id from books where title like '%毛泽东全集 第35卷%'").fetchone()
if r:
    for i, ch in enumerate(c.execute("select page_from, substr(content,1,400) from book_chunks where book_id=? order by page_from limit 3", (r[0],))):
        o.append("  --- 块%d (页%s) ---" % (i + 1, ch[0]))
        o.append("  " + (ch[1] or "").replace("\n", " ")[:380])

open(r"E:\desktop\media\_c_classify.txt", "w", encoding="utf-8").write("\n".join(o))
print("\n".join("%s: %d" % (g, len(r)) for g, r in groups.items()))
