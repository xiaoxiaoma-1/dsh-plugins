# -*- coding: utf-8 -*-
"""把素材提炼成观点原子，写进 atoms。

三种源：
  posts        稿库（1631 条 / 178.9 万字 / 145 个作者）
  live         直播片段（297 条 / 33.2 万字）
  book         书块（241276 块 / 2.35 亿字，最大头）

用法：
  python extract_views.py --src posts --limit 10            # 小样
  python extract_views.py --src posts --limit 0             # 全量（0=不限）
  python extract_views.py --src book  --limit 0 --conc 64
断点续跑：已处理过的（atoms 里同 src_id 的）自动跳过。
"""
import argparse
import io
import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.request
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = r"E:\desktop\media\workbench.db"
BASE = "http://127.0.0.1:8326/v1"
KEYFILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
LOG = r"E:\desktop\media\_extract_views.log"
STATE = r"E:\desktop\media\_extract_state.json"

SYS = """你从一段中文原文里提炼「观点原子」。观点原子 = 一个人对一件事的判断、主张、看事的角度，或者是可复用的方法/技能。

只输出 JSON，不要 markdown，不要解释。格式：
{"items":[{"knowledge":"一句完整的判断，20-60字，必须能独立看懂","type":"insight|principle|case|tool|method|anti-pattern","topics":["1-2个主题标签"],"confidence":"high|medium|low"}]}

规则：
1. knowledge 必须是原文里那个人自己的判断，不是你的总结，不要写成"他说明了…"
2. 带数字、带场景、带因果的优先，空泛的不要
3. **条数不设上限**：原文里有多少值得单独立住的判断就提多少，干货拉满就给几十条；**没有就返回 {"items":[]}，绝对不要为了凑数硬挤**。判断标准是"这句话能不能单独拿出去讲"，不能就不要
4. 原文里的第一人称保留（"我"就是原作者）"""

BUBBLE = "http://127.0.0.1:8326/api/dsh-bubble/push"


def push_bubble(pct, detail, state="running"):
    """把进度推给悬浮球。失败就算了，绝不影响提炼。"""
    try:
        data = json.dumps({"type": "task", "id": "extract-views", "title": "提炼观点",
                           "pct": int(pct), "detail": detail, "state": state}).encode("utf-8")
        hdr = {"content-type": "application/json"}
        k = api_key()
        if k:
            hdr["authorization"] = "Bearer " + k
        req = urllib.request.Request(BUBBLE, data=data, headers=hdr)
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass


lock = threading.Lock()
counter = {"ok": 0, "fail": 0, "atoms": 0, "skip": 0}


def log(msg):
    line = time.strftime("%H:%M:%S") + " " + msg
    with lock:
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
        print(line, flush=True)


def api_key():
    try:
        return open(KEYFILE, encoding="utf-8").read().strip()
    except Exception:
        return ""


def call_llm(text, tries=3):
    key = api_key()
    if not key:
        raise RuntimeError("读不到 api-key: " + KEYFILE)
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": text[:4000]}],
        "temperature": 0.5,
        "max_tokens": 4000,
    }).encode("utf-8")
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                BASE + "/chat/completions", data=body,
                headers={"content-type": "application/json", "authorization": "Bearer " + key})
            with urllib.request.urlopen(req, timeout=240) as r:
                j = json.loads(r.read().decode("utf-8"))
            c = j["choices"][0]["message"]["content"]
            m = re.search(r"\{[\s\S]*\}", c)
            if not m:
                return []
            return json.loads(m.group(0)).get("items") or []
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(str(last))


def ensure_cols(c):
    cols = [r[1] for r in c.execute("PRAGMA table_info(atoms)")]
    if "src_id" not in cols:
        c.execute("ALTER TABLE atoms ADD COLUMN src_id TEXT")
    # 一条原文要能出多个观点，所以不能是唯一索引
    c.execute("DROP INDEX IF EXISTS idx_atoms_src")
    c.execute("CREATE INDEX IF NOT EXISTS idx_atoms_src2 ON atoms(src_id)")
    c.commit()


def rows_for(c, src, limit):
    if src == "posts":
        q = ("select id, author, text, url, date from posts "
             "where text is not null and length(text) > 200 order by created_at desc")
    elif src == "live":
        q = ("select id, author, text, '', '' from live_segments "
             "where text is not null and length(text) > 200 order by created_at desc")
    elif src == "book":
        q = ("select ch.id, coalesce(b.title,''), ch.content, '', '' "
             "from book_chunks ch left join books b on b.id = ch.book_id "
             "where ch.content is not null and length(ch.content) > 400 order by ch.id")
    else:
        raise SystemExit("unknown src " + src)
    done = set()
    for (sid,) in c.execute("select src_id from atoms where src_id is not null"):
        parts = str(sid).split(":")
        if len(parts) >= 2:
            done.add(parts[0] + ":" + parts[1])
    out = [r for r in c.execute(q) if (src + ":" + str(r[0])) not in done]
    # 连续失败 3 次的跳过，不让它每轮都重试（长文会一直超时）
    try:
        c.execute("CREATE TABLE IF NOT EXISTS extract_fail (src_id TEXT PRIMARY KEY, tries INTEGER NOT NULL DEFAULT 0)")
        dead = set(x[0] for x in c.execute("select src_id from extract_fail where tries >= 3"))
        if dead:
            before = len(out)
            out = [r for r in out if (src + ":" + str(r[0])) not in dead]
            if before != len(out):
                print(f"跳过 {before - len(out)} 篇连续失败3次的")
    except Exception:
        pass
    return out[:limit] if limit else out


def fail_count(c, sid):
    try:
        c.execute("CREATE TABLE IF NOT EXISTS extract_fail (src_id TEXT PRIMARY KEY, tries INTEGER NOT NULL DEFAULT 0)")
    except Exception:
        pass
    r = c.execute("select tries from extract_fail where src_id=?", (sid,)).fetchone()
    return r[0] if r else 0


def mark_fail(c, sid):
    try:
        c.execute("insert into extract_fail (src_id, tries) values (?,1) "
                  "on conflict(src_id) do update set tries = tries + 1", (sid,))
        c.commit()
    except Exception:
        pass


def worker(src, queue, idx):
    while True:
        with lock:
            if not queue:
                return
            row = queue.pop(0)
        rid_, author, text, url, day = row
        sid = src + ":" + str(rid_)
        try:
            items = call_llm(text or "")
        except Exception as e:
            with lock:
                counter["fail"] += 1
            try:
                c3 = sqlite3.connect(DB, timeout=20)
                mark_fail(c3, sid)
                c3.close()
            except Exception:
                pass
            log(f"[{src}] 失败 {rid_} {str(e)[:80]}")
            continue
        if not items:
            with lock:
                counter["skip"] += 1
            continue
        c2 = sqlite3.connect(DB, timeout=30)
        n = 0
        for k_i, it in enumerate(items):
            k = str(it.get("knowledge") or "").strip()
            if len(k) < 8:
                continue
            aid = "x" + uuid.uuid4().hex[:12]
            try:
                c2.execute(
                    "insert or ignore into atoms (id, author, knowledge, original, url, date, topics,"
                    " skills, type, confidence, usage, created_at, hidden, flag, src_id)"
                    " values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (aid, author or "", k, (text or "")[:2000], url or "", day or "",
                     json.dumps(it.get("topics") or [], ensure_ascii=False), "",
                     str(it.get("type") or "insight"), str(it.get("confidence") or "medium"),
                     0, time.strftime("%Y-%m-%dT%H:%M:%S"), 0, src, sid + ":" + str(k_i)))
                n += 1
            except Exception:
                pass
        c2.commit()
        c2.close()
        with lock:
            counter["ok"] += 1
            counter["atoms"] += n
        if counter["ok"] % 25 == 0:
            try:
                done_n = counter["ok"]; tot_n = done_n + len(queue)
                push_bubble(round(done_n / max(1, tot_n) * 100), f"{done_n}/{tot_n} 篇 · 出 {counter['atoms']} 条观点")
            except Exception:
                pass
            log(f"进度 已处理 {counter['ok']} 条 / 出观点 {counter['atoms']} 条 / 失败 {counter['fail']} / 空 {counter['skip']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, choices=["posts", "live", "book"])
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--conc", type=int, default=32)
    a = ap.parse_args()

    c = sqlite3.connect(DB)
    ensure_cols(c)
    rows = rows_for(c, a.src, a.limit)
    c.close()
    if not rows:
        log("没有待处理的（可能全跑过了），退出")
        return
    log(f"[{a.src}] 待处理 {len(rows)} 条，并发 {a.conc}")
    push_bubble(0, f"{len(rows)} 条待提炼")
    t0 = time.time()
    q = list(rows)
    ths = [threading.Thread(target=worker, args=(a.src, q, i), daemon=True) for i in range(a.conc)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    push_bubble(100, f"完成 · 出 {counter['atoms']} 条观点", "done")
    log(f"[{a.src}] 完成：源 {counter['ok']} 条 / 观点 {counter['atoms']} 条 / 失败 {counter['fail']} / 无观点 {counter['skip']} / 用时 {(time.time()-t0)/60:.1f} 分钟")


if __name__ == "__main__":
    main()
