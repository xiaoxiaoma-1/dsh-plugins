# -*- coding: utf-8 -*-
"""按用户指令出清理清单：毛选 / 残书 / 王阳明碎片 / C档四类"""
import json, re, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
d = json.load(open(r"E:\desktop\media\_quality_tier.json", encoding="utf-8"))
o = []

def info(bid):
    t = c.execute("select title from books where id=?", (bid,)).fetchone()
    n = c.execute("select coalesce(sum(length(content)),0) from book_chunks where book_id=?", (bid,)).fetchone()[0]
    p = c.execute("select coalesce(pages,0) from books where id=?", (bid,)).fetchone()[0]
    return (t[0] if t else "?"), n, p

# ============ 一、毛选 ============
o.append("========== 一、毛选现状 ==========")
mao = []
for bid in d:
    t, n, p = info(bid)
    if re.search(r"(毛泽东|毛选|毛主席|毛泽东选集)", t):
        mao.append((t, n, p, d[bid].get("tier"), d[bid].get("score")))
o.append("库里毛相关共 %d 本" % len(mao))
sel = [x for x in mao if "选集" in x[0]]
allb = [x for x in mao if "全集" in x[0]]
oth = [x for x in mao if "选集" not in x[0] and "全集" not in x[0]]
o.append("")
o.append("【毛泽东选集（你要的）】%d 本" % len(sel))
for t, n, p, tier, sc in sorted(sel, key=lambda x: -x[1]):
    o.append("   %s %s分｜%s字 %s页｜%s" % (tier, sc, n, p, t[:50]))
o.append("")
o.append("【毛泽东全集（52卷本，你说不要的）】%d 本" % len(allb))
o.append("   合计 %d 字" % sum(x[1] for x in allb))
for t, n, p, tier, sc in sorted(allb, key=lambda x: x[0]):
    o.append("   %s %s分｜%s字 %s页｜%s" % (tier, sc, n, p, t[:44]))
o.append("")
o.append("【其他毛相关】%d 本" % len(oth))
for t, n, p, tier, sc in sorted(oth, key=lambda x: -x[1])[:20]:
    o.append("   %s %s分｜%s字 %s页｜%s" % (tier, sc, n, p, t[:50]))

# ============ 二、165 本残书的干货情况 ============
o.append("")
o.append("========== 二、165 本残书（<5000字）里有干货吗 ==========")
res = []
for bid, v in d.items():
    t, n, p = info(bid)
    if 0 < n < 5000:
        res.append((v.get("tier"), v.get("score"), n, t, v.get("why")))
from collections import Counter
cnt = Counter(x[0] for x in res)
o.append("共 %d 本：A %d / B %d / C %d" % (len(res), cnt["A"], cnt["B"], cnt["C"]))
o.append("")
o.append("【A 档，有干货，%d 本 —— 留】" % cnt["A"])
for tier, sc, n, t, why in sorted([x for x in res if x[0] == "A"], key=lambda x: -x[1]):
    o.append("   %s分 %s字｜%s" % (sc, n, t[:52]))
o.append("")
o.append("【B 档，一般，%d 本】" % cnt["B"])
for tier, sc, n, t, why in sorted([x for x in res if x[0] == "B"], key=lambda x: -x[1])[:40]:
    o.append("   %s分 %s字｜%s｜%s" % (sc, n, t[:46], why))
o.append("")
o.append("【C 档，没干货，%d 本 —— 删】" % cnt["C"])
for tier, sc, n, t, why in sorted([x for x in res if x[0] == "C"], key=lambda x: -x[1]):
    o.append("   %s分 %s字｜%s｜%s" % (sc, n, t[:46], why))

# ============ 三、王阳明碎片 ============
o.append("")
o.append("========== 三、王阳明（保留 57 本，碎片删） ==========")
wym = []
for bid, v in d.items():
    t, n, p = info(bid)
    if re.search(r"(王阳明|阳明|传习录|心学)", t):
        wym.append((t, n, p, v.get("tier"), v.get("score")))
o.append("王阳明相关 %d 本，其中字数<30000 的碎片：" % len(wym))
for t, n, p, tier, sc in sorted([x for x in wym if x[1] < 30000], key=lambda x: x[1]):
    o.append("   %s字 %s页 %s%s分｜%s" % (n, p, tier, sc, t[:52]))
o.append("（注：库里没有《知易行难王阳明》这本）")

# ============ 四、C 档四类明细 ============
o.append("")
o.append("========== 四、C 档 141 本四类明细 ==========")
NOVEL = re.compile(r"(小说|叙事|情节|文学|散文|诗歌|诗集|玄幻|言情|穿越|晋江|琅琊榜|上册|下册|共\d册|三部曲|传奇)")
GARBAGE = re.compile(r"(乱码|符号|无有效|拼凑|跳跃|重复|图片|碎片|不连续|扫描|广告|招商)")
groups = {"小说": [], "乱码碎片": [], "付费文章/老A": [], "泛泛但正常": []}
for bid, v in d.items():
    if v.get("tier") != "C":
        continue
    t, n, p = info(bid)
    why = v.get("why") or ""
    row = (t, n, p, v.get("score"), v.get("kind"), why)
    if "付费文章" in t or "老A" in t:
        groups["付费文章/老A"].append(row)
    elif NOVEL.search(t + why):
        groups["小说"].append(row)
    elif GARBAGE.search(why):
        groups["乱码碎片"].append(row)
    else:
        groups["泛泛但正常"].append(row)
for g in ["小说", "乱码碎片", "付费文章/老A", "泛泛但正常"]:
    rows = groups[g]
    o.append("")
    o.append("【%s】%d 本，合计 %d 字" % (g, len(rows), sum(x[1] for x in rows)))
    for t, n, p, sc, kind, why in sorted(rows, key=lambda x: -x[1]):
        o.append("   %s分 %s字 %s%s｜%s｜%s" % (sc, n, p, kind, t[:42], why))

open(r"E:\desktop\media\_clean_plan.txt", "w", encoding="utf-8").write("\n".join(str(x) for x in o))
print("毛相关 %d（选集 %d / 全集 %d / 其他 %d）" % (len(mao), len(sel), len(allb), len(oth)))
print("残书 165：A %d B %d C %d" % (cnt["A"], cnt["B"], cnt["C"]))
print("C档: " + " / ".join("%s %d" % (g, len(r)) for g, r in groups.items()))
