"""直播片段级分类：精简稿切块 → 逐块判大类/子类 → 相邻同类合并成片段 → 入库

产物：workbench.db 新表 live_segments；另存 E:\\desktop\\media\\_live_segments.json
用法：python segment_classify.py [并发]
"""
import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
COND = r"E:\desktop\media\_condense"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
CHUNK = 800

TREE = {
    "权谋与政治": ["权力与博弈", "人情世故", "体制与生存", "毛选"],
    "商业与变现": ["搞钱路径", "定价与成交", "流量获客", "团队与合伙"],
    "内容创作": ["选题", "标题与开头", "结构与节奏", "平台规则", "起号与增长"],
    "心理与人性": ["自我认知", "情绪", "关系", "欲望与动机"],
    "语言与思维": ["表达与说服", "逻辑", "认知模型", "反常识"],
    "AI 与工具": ["AI 用法", "提示词", "自动化", "效率工具"],
    "国学与哲学": ["心学", "道家与易", "人生选择", "历史人物"],
    "身心与生活": ["身体", "冥想", "阅读", "生活方式"],
}
ALL = {s for v in TREE.values() for s in v}
SYS = "你是中文内容分类器。只能从给定清单里选，绝不造词。只输出 JSON。"
TREE_TXT = "\n".join(f"{d}：{' / '.join(v)}" for d, v in TREE.items())
PROMPT = """来源：直播｜博主：{author}
内容：
{text}

【大类】{doms}
【大类→子类】
{tree}

这段主要在讲什么？输出 JSON：
{{"d":"大类","subs":["子类1"],"conf":0.0-1.0}}
要求：d 必须是大类之一；subs 1-2 个，必须属于 d；讲"怎么做/怎么赚钱/怎么说话"这类方法归方法所在大类。"""

_lock = threading.Lock()
_n = 0
_tot = 0
_t0 = 0


def call(text, author, tries=3):
    body = json.dumps({"model": MODEL, "temperature": 0.2, "max_tokens": 300,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(
                                        author=author, text=text,
                                        doms=" / ".join(TREE.keys()), tree=TREE_TXT)}]}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=90) as r:
                j = json.load(r)
            s = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            s = s[s.find("{"): s.rfind("}") + 1]
            o = json.loads(s)
            d = o.get("d")
            subs = [x for x in (o.get("subs") or []) if x in ALL and (d is None or x in TREE.get(d, []))]
            if d in TREE and subs:
                return {"d": d, "subs": subs[:2], "conf": float(o.get("conf") or 0.5)}
        except Exception:
            time.sleep(1 + i)
    return {"d": None, "subs": [], "conf": 0.0}


def work(args):
    global _n
    post_id, author, idx, text = args
    o = call(text, author)
    with _lock:
        _n += 1
        if _n % 40 == 0:
            el = time.time() - _t0
            print(f"  块 {_n}/{_tot} | {el:.0f}s | 剩约 {el/_n*(_tot-_n)/60:.0f} 分钟", flush=True)
    return post_id, idx, text, o


def chunks_of(text):
    out, buf = [], ""
    for ch in text:
        buf += ch
        if len(buf) >= CHUNK:
            cut = -1
            for m in ("。", "！", "？", "\n", "，", "；"):
                k = buf.rfind(m, max(0, len(buf) - 100))
                if k > cut:
                    cut = k
            if cut > CHUNK * 0.5:
                out.append(buf[:cut + 1]); buf = buf[cut + 1:]
            else:
                out.append(buf); buf = ""
    if buf.strip():
        out.append(buf)
    return [c for c in out if c.strip()]


def main():
    global _tot, _t0
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    posts = c.execute("select id, author from posts where kind='live'").fetchall()
    c.close()

    jobs, meta = [], {}
    for p in posts:
        f = os.path.join(COND, p["id"] + "_精简.txt")
        if not os.path.exists(f):
            continue
        text = open(f, encoding="utf-8").read()
        author = re.sub(r"^直播：", "", p["author"] or "").split(" · ")[0].strip()
        chs = chunks_of(text)
        meta[p["id"]] = {"author": author, "chunks": chs, "res": {}}
        for i, ch in enumerate(chs):
            jobs.append((p["id"], author, i, ch))
    _tot = len(jobs); _t0 = time.time()
    print(f"场次 {len(meta)}｜块 {_tot}｜并发 {workers}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for pid, idx, text, o in ex.map(work, jobs):
            meta[pid]["res"][idx] = (text, o)

    # 合并相邻同类块 → 片段
    rows = []
    for pid, m in meta.items():
        segs, cur = [], None
        for i in range(len(m["chunks"])):
            text, o = m["res"].get(i, (m["chunks"][i], {"d": None, "subs": [], "conf": 0}))
            key = (o.get("d"), (o.get("subs") or [None])[0])
            if cur and key != (None, None) and (cur["d"], cur["subs"][0] if cur["subs"] else None) == key:
                cur["text"] += "\n" + text
                cur["chars"] += len(text)
                cur["conf"] = round(min(cur["conf"], o.get("conf") or 0.5), 2)
            else:
                if cur:
                    segs.append(cur)
                cur = {"post_id": pid, "author": m["author"], "d": o.get("d"),
                       "subs": o.get("subs") or [], "conf": o.get("conf") or 0,
                       "text": text, "chars": len(text)}
        if cur:
            segs.append(cur)
        for n, s in enumerate(segs, 1):
            s["seg_no"] = n
            rows.append(s)

    n_labeled = sum(1 for r in rows if r["d"])
    print(f"\n片段 {len(rows)} 个（有标签 {n_labeled}，无标签 {len(rows)-n_labeled}）")
    from collections import Counter
    print("大类分布:", Counter(r["d"] for r in rows).most_common())

    with open(r"E:\desktop\media\_live_segments.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    c = sqlite3.connect(DB)
    c.execute("""create table if not exists live_segments(
        id text primary key, post_id text, author text, seg_no integer,
        topic text, sub text, subs text, conf real, chars integer, text text, created_at text)""")
    c.execute("delete from live_segments")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    for r in rows:
        c.execute("insert into live_segments(id,post_id,author,seg_no,topic,sub,subs,conf,chars,text,created_at)"
                  " values(?,?,?,?,?,?,?,?,?,?,?)",
                  (f"{r['post_id']}_s{r['seg_no']}", r["post_id"], r["author"], r["seg_no"],
                   r["d"], (r["subs"][0] if r["subs"] else ""), ",".join(r["subs"]),
                   r["conf"], r["chars"], r["text"], now))
    c.commit(); c.close()
    print("已入库 live_segments；总耗时 %.1f 分钟" % ((time.time() - _t0) / 60))


if __name__ == "__main__":
    main()
