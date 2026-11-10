"""
直播「有没有连麦」文本粗筛（零成本，只看文字）

判据（连麦 = 观众提问 + 主播回应）：
- 观众侧标记：你好 / 我想问 / 请问 / 请教 / 我是… / 我在… / 我的情况 / 能听到吗 / 在吗 / 喂
- 互动侧标记：评论区 / 连麦 / 上麦 / 大家
- 问句密度：含 ？ 或 「吗/呢」结尾的短句占比
输出：按「连麦可能性」排序的全表，落 md 备查。
"""
import json
import re
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"
OUT = r"E:\desktop\media\_live_连麦初筛.md"

VIEWER = ["你好", "我想问", "请问", "请教", "我的情况", "我今年", "我在", "我是做", "能听到吗",
          "能听到", "在吗", "喂喂", "老师好", "大神", "帮我看", "怎么办"]
HOST = ["评论区", "扣个", "点个关注", "小黄车", "直播间", "连麦", "上麦", "刷刷", "家人们"]

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
rows = c.execute("select id, author, date, text, length(text) n from posts where kind='live'").fetchall()
c.close()

res = []
for r in rows:
    t = r["text"] or ""
    v = {k: t.count(k) for k in VIEWER}
    h = {k: t.count(k) for k in HOST}
    vsum = sum(v.values())
    hsum = sum(h.values())
    sents = [s for s in re.split(r"[。！？\n]", t) if s.strip()]
    qsent = sum(1 for s in sents if "？" in s or s.rstrip().endswith(("吗", "呢")))
    qdens = qsent / max(len(sents), 1)
    # 打分：观众侧标记权重最高，问句密度次之
    score = vsum * 2 + qdens * 10
    res.append({
        "id": r["id"], "author": r["author"], "date": (r["date"] or "")[:10], "chars": r["n"],
        "viewer_hits": vsum, "host_hits": hsum, "q_density": round(qdens, 3), "score": round(score, 1),
        "top_marks": ", ".join(f"{k}×{n}" for k, n in sorted(v.items(), key=lambda x: -x[1]) if n)[:80],
        "head": t[:100].replace("\n", " "),
    })

res.sort(key=lambda x: -x["score"])
with open(OUT, "w", encoding="utf-8") as f:
    f.write(f"# 直播连麦初筛（{len(res)} 场）\n\n")
    f.write("判据：观众侧标记词次数×2 + 问句密度×10。**只筛不判死**，高分场次建议人工看开头。\n\n")
    f.write("| 场次 | 主播 | 日期 | 字数 | 观众标记 | 互动标记 | 问句密度 | 分 | 命中词 |\n|---|---|---|---|---|---|---|---|---|\n")
    for x in res:
        f.write(f"| {x['id']} | {x['author']} | {x['date']} | {x['chars']} | {x['viewer_hits']} | "
                f"{x['host_hits']} | {x['q_density']} | {x['score']} | {x['top_marks']} |\n")

print(f"共 {len(res)} 场\n")
print(f"{'分':>6} {'观众':>4} {'问密度':>6} {'字数':>6}  {'主播':<14} {'日期':<10}")
for x in res:
    print(f"{x['score']:>6} {x['viewer_hits']:>4} {x['q_density']:>6} {x['chars']:>6}  {x['author'][:12]:<14} {x['date']}")

print("\n=== 前 5 高分的开头 ===")
for x in res[:5]:
    print(f"\n[{x['score']}] {x['author']} {x['date']} | 标记: {x['top_marks']}")
    print("   ", x["head"])

print("\n产物：", OUT)
