# -*- coding: utf-8 -*-
"""给每本书生成一张「书卡」：核心主张 + 5-10 个洞察 + 适合谁 + 值不值得精读。

用法：
  python book_card.py --sample 5     先跑 5 本看效果
  python book_card.py --go           全量跑（跳过已有的）
  python book_card.py --go --conc 16 并发数
"""
import argparse
import io
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"
LOG = r"E:\desktop\media\book_card.log"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

SYSTEM = """你是资深书评人。给你一本书的抽样内容，你要给它做一张「书卡」，让读者一眼判断要不要读。

严格只输出 JSON，不要 markdown，不要解释：
{
  "gist": "这本书核心在讲什么，一句话，40 字以内",
  "insights": ["这本书最有价值的洞察，5-10 条，每条 20-40 字，要具体不要空话"],
  "for_who": "适合谁读，一句话",
  "solves": "它能解决什么具体问题，一句话",
  "verdict": "精读 或 翻翻 或 跳过",
  "why": "给出这个判断的理由，40 字以内"
}

判断标准：
- 精读：有独特的论证体系或大量一手材料，值得逐章读
- 翻翻：有几个好观点但整体注水，抽着看就行
- 跳过：内容空洞、拼凑、或明显是二手转述
不要因为书有名气就往高了判。"""


def log(m):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), m)
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def ensure_table(c):
    c.execute("""create table if not exists book_card(
        book_id text primary key,
        gist text, insights text, for_who text, solves text,
        verdict text, why text, created_at text)""")
    c.commit()


def sample_book(c, book_id, title, npages):
    """抽样：目录 + 开头 + 均匀中间 + 结尾，总共约 1.5 万字"""
    rows = c.execute(
        "select heading, content, page_from from book_chunks where book_id=? order by page_from, id",
        (book_id,)).fetchall()
    if not rows:
        return ""
    n = len(rows)
    parts = []
    # 目录/前言（前 3 块）
    for r in rows[:3]:
        parts.append(r[1])
    # 均匀取中间 8 块
    if n > 6:
        step = max(1, (n - 6) // 8)
        for i in range(3, n - 3, step):
            if len(parts) >= 11:
                break
            parts.append(rows[i][1])
    # 结尾 2 块
    for r in rows[-2:]:
        parts.append(r[1])
    txt = "\n\n---\n\n".join(parts)
    return txt[:16000]


def call_ai(title, content):
    prompt = ("书名：%s\n\n抽样内容：\n%s" % (title, content))
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
        "temperature": 0.3, "max_tokens": 2200,
    }).encode("utf-8")
    req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                 headers={"content-type": "application/json",
                                          "authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=300) as r:
        j = json.loads(r.read().decode("utf-8"))
    return (j["choices"][0]["message"]["content"] or "").strip()


def parse(obj_raw):
    m = re.search(r"\{[\s\S]*\}", obj_raw or "")
    if not m:
        return None
    try:
        o = json.loads(m.group(0))
    except Exception:
        return None
    if not o.get("gist"):
        return None
    ins = o.get("insights") or []
    if not isinstance(ins, list):
        ins = [str(ins)]
    return {
        "gist": str(o.get("gist"))[:200],
        "insights": [str(x)[:200] for x in ins][:10],
        "for_who": str(o.get("for_who") or "")[:200],
        "solves": str(o.get("solves") or "")[:200],
        "verdict": str(o.get("verdict") or "")[:8],
        "why": str(o.get("why") or "")[:200],
    }


def one(bid):
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        r = c.execute("select title, pages from books where id=?", (bid,)).fetchone()
        if not r:
            return (bid, None, "书不存在")
        name = r["title"] or ""
        content = sample_book(c, bid, name, r["pages"] or 0)
        if len(content) < 500:
            return (bid, None, "内容太少")
        raw = call_ai(name, content)
        o = parse(raw)
        if not o:
            return (bid, None, "AI 输出解析失败")
        c.execute(
            "insert or replace into book_card(book_id,gist,insights,for_who,solves,verdict,why,created_at)"
            " values(?,?,?,?,?,?,?,?)",
            (bid, o["gist"], json.dumps(o["insights"], ensure_ascii=False),
             o["for_who"], o["solves"], o["verdict"], o["why"],
             time.strftime("%Y-%m-%d %H:%M:%S")))
        c.commit()
        return (bid, o, None)
    except Exception as e:
        return (bid, None, str(e)[:120])
    finally:
        c.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--conc", type=int, default=16)
    a = ap.parse_args()

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    ensure_table(c)
    done = {r[0] for r in c.execute("select book_id from book_card")}
    rows = c.execute("select id, title from books order by rowid").fetchall()
    todo = [(r["id"], r["title"]) for r in rows if r["id"] not in done]
    log("书库 %d 本 | 已有书卡 %d | 待做 %d" % (len(rows), len(done), len(todo)))

    if a.sample:
        todo = todo[:a.sample]
        log("抽样模式：只跑前 %d 本" % len(todo))
    if not a.go and not a.sample:
        log("加 --go 全量跑，或 --sample N 抽样")
        return

    t0 = time.time()
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=a.conc) as ex:
        futs = {ex.submit(one, bid): (bid, name) for bid, name in todo}
        for i, f in enumerate(as_completed(futs), 1):
            bid, name = futs[f]
            _, o, err = f.result()
            if o:
                ok += 1
                log("[%d/%d] ✓ %s | %s | %s" % (i, len(todo), name[:24], o["verdict"], o["gist"][:40]))
            else:
                fail += 1
                log("[%d/%d] ✗ %s | %s" % (i, len(todo), name[:24], err))
    log("完成：成功 %d / 失败 %d / 用时 %.1f 分钟" % (ok, fail, (time.time() - t0) / 60))
    log("全书卡数: %d" % c.execute("select count(*) from book_card").fetchone()[0])
    c.close()


if __name__ == "__main__":
    main()
