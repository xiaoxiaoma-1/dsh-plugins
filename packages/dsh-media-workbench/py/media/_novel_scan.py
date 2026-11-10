# -*- coding: utf-8 -*-
"""全库小说/文学嫌疑扫描（不调用模型，靠 why + 标题特征）"""
import json, re, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
d = json.load(open(r"E:\desktop\media\_quality_tier.json", encoding="utf-8"))

FICT = re.compile(r"(小说|叙事|情节|文学|散文|诗歌|诗集|玄幻|言情|穿越|重生|武侠|仙侠|架空|传奇故事|话本|演义)")
TITLE = re.compile(r"(小说|传（|全传|演义|传奇|三部曲|共\d册|上册|下册|第[一二三四五六]册|琅琊榜|赘婿|龙王|战神|逆袭.*(全集|完结)|完结|txt|\[精品\]$)")

novel = {}
for bid, v in d.items():
    t = c.execute("select title from books where id=?", (bid,)).fetchone()[0] or ""
    why = v.get("why") or ""
    if FICT.search(why) or TITLE.search(t):
        novel[bid] = (t, v.get("tier"), v.get("score"), why)

o = ["小说/文学虚构嫌疑 %d 本" % len(novel)]
for bid, (t, tier, sc, why) in sorted(novel.items(), key=lambda x: (x[1][1] or "", -(x[1][2] or 0))):
    o.append("  %s %s分｜%s｜%s" % (tier, sc, t[:50], why))
open(r"E:\desktop\media\_novel_scan.txt", "w", encoding="utf-8").write("\n".join(o))
print("嫌疑 %d 本" % len(novel))
print("\n".join(o[:12]))
