# -*- coding: utf-8 -*-
"""每日灵感：从原子库里挑 5 条素材，输出 JSON，等 AI 补「怎么用」。

挑选原则：
- 优先 confidence=high，其次 medium
- 主题要分散（5 条尽量不全落在一个 topic 上）
- 知识点的长度要在能独立成立的区间（40-200 字）
- 同一个 topic 每次最多取 1 条，保证多样性

输出：E:\\desktop\\hot\\idea-YYYY-MM-DD.json
结构：{ date, generated_at, items:[{id, knowledge, original, topics, type, confidence, url}] }
"""
import json
import os
import random
import re
import sqlite3
import sys
from datetime import datetime

DB = r"E:\desktop\media\workbench.db"
OUT_DIR = r"E:\desktop\hot"

# 代码 / 命令片段，不是方法论
CODE_PAT = re.compile(
    r"(nohup|/dev/null|sudo\s|\bgit\s|\bnpm\s|\bpip\s|\bdocker\s|&gt;|&lt;|</|\{\s*\}|=&gt;|^\s*[\$#>])",
    re.I,
)


def is_code(s):
    return bool(CODE_PAT.search(s or ""))

# 工作记录 / 话术模板 / 敏感话题，都不是可复用的方法论，统一排除
NOISE = [
    # 工作流水账
    "%下一步%", "%刚刚%", "%今天%", "%昨天%", "%刚才%",
    "%我已经%", "%我在%", "%接上%", "%跑通%", "%部署%",
    "%吊打%", "%体感%", "%测试了%",
    # 营销话术模板
    "%xxx%", "%你是不是%", "%阅读量%", "%点赞%", "%关注我%",
    "%分享一个%", "%三个技巧%", "%干货%",
    # 敏感话题，脱离语境会被误读
    "%通婚%", "%血统%", "%种族%", "%政治%", "%宗教%",
    "%女权%", "%性别%", "%移民%",
]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    stamp = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(DB):
        print(f"[skip] 数据库不存在 {DB}")
        return

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    noise_where = " AND ".join(["knowledge NOT LIKE ?"] * len(NOISE))
    rows = cur.execute(
        f"""
        SELECT id, knowledge, original, topics, type, confidence, url
        FROM atoms
        WHERE length(knowledge) BETWEEN 55 AND 200
          AND knowledge NOT LIKE '%http%'
          AND confidence IN ('high','medium')
          AND {noise_where}
          AND type IN ('principle','method','anti-pattern','insight')
        ORDER BY
          CASE type WHEN 'principle' THEN 0 WHEN 'method' THEN 1
                    WHEN 'anti-pattern' THEN 2 ELSE 3 END,
          CASE confidence WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
          RANDOM()
        LIMIT 300
        """,
        NOISE,
    ).fetchall()
    con.close()

    picked = []
    used_topics = set()
    used_types = {}
    for r in rows:
        if is_code(r["knowledge"]):
            continue
        try:
            topics = json.loads(r["topics"] or "[]")
        except Exception:
            topics = []
        main_topic = topics[0] if topics else "未分类"
        if main_topic in used_topics:
            continue
        # 类型分散：同一 type 最多 3 条
        t = r["type"] or "unknown"
        if used_types.get(t, 0) >= 3:
            continue
        used_topics.add(main_topic)
        used_types[t] = used_types.get(t, 0) + 1
        picked.append({
            "id": r["id"],
            "knowledge": r["knowledge"],
            "original": r["original"],
            "topics": topics,
            "type": r["type"],
            "confidence": r["confidence"],
            "url": r["url"],
        })
        if len(picked) >= 5:
            break

    # 第二遍：主题太少时放宽（同一 topic 最多 2 条），保证凑满 5 条
    if len(picked) < 5:
        topic_count = {}
        for p in picked:
            t0 = p["topics"][0] if p["topics"] else "未分类"
            topic_count[t0] = topic_count.get(t0, 0) + 1
        picked_ids = {p["id"] for p in picked}
        for r in rows:
            if len(picked) >= 5:
                break
            if r["id"] in picked_ids or is_code(r["knowledge"]):
                continue
            try:
                topics = json.loads(r["topics"] or "[]")
            except Exception:
                topics = []
            main_topic = topics[0] if topics else "未分类"
            if topic_count.get(main_topic, 0) >= 2:
                continue
            t = r["type"] or "unknown"
            if used_types.get(t, 0) >= 3:
                continue
            topic_count[main_topic] = topic_count.get(main_topic, 0) + 1
            used_types[t] = used_types.get(t, 0) + 1
            picked_ids.add(r["id"])
            picked.append({
                "id": r["id"],
                "knowledge": r["knowledge"],
                "original": r["original"],
                "topics": topics,
                "type": r["type"],
                "confidence": r["confidence"],
                "url": r["url"],
            })

    payload = {
        "date": stamp,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(picked),
        "items": picked,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"idea-{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[idea] 挑了 {len(picked)} 条 -> {path}")
    for i, p in enumerate(picked, 1):
        topic = p["topics"][0] if p["topics"] else "未分类"
        print(f"\n--- {i}. [{topic}] ({p['type']}/{p['confidence']}) ---")
        print(p["knowledge"][:150])


if __name__ == "__main__":
    main()
