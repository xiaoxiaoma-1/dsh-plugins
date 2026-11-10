# -*- coding: utf-8 -*-
"""直播 / 短视频口语稿 → 六板块拆解，写进 split_items。

和 extract_split.py（拆书）同一套板子、同一个网关，但 prompt 针对口语稿重写：
直播是「说话」，不是「写文章」。要能听出他在教什么、把口语里的做法挑出来，
而不是把碎句原样搬进库。

重点：dry（干货）不是「一句道理」，而是「一个能照做的做法 / 一组有顺序的动作」。
用户要的是可复用的小技巧，不是需要再加工一遍的半成品。

用法：
  python split_live.py --kind live --limit 3      # 试 3 块看质量
  python split_live.py --kind live                # 只做直播
  python split_live.py --kind all                 # live + douyin 全量
"""
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DB = r"E:\desktop\media\workbench.db"
GATEWAY = "http://127.0.0.1:8326/v1/chat/completions"
KEYFILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
LOG = r"E:\desktop\media\split_live.log"

BOARDS = {"hook": "钩子", "dry": "干货", "case": "案例",
          "quote": "金句", "avoid": "避坑", "qa": "问答"}

CHUNK = 1400      # 每块字数
OVERLAP = 120     # 块间重叠，避免把一句话切成两半

SYS = """你是中文内容编辑，正在处理某位博主直播/短视频的口语转写稿。

从这段话里挑出「以后做内容能直接拿来用」的素材，按六个板块归类。
只输出 JSON 数组，不要解释、不要 markdown 代码块。
每个元素：{"board":"hook|dry|case|quote|avoid|qa","text":"原文原话","note":"不超过18字的提炼"}

各板块标准：
- hook  开头第一句能抓人的话（必须是原文，不改写）
- dry   干货 = 一个能照做的做法，或一组有顺序的步骤。**不是一句空道理**
        例：「先发 100 条测试选题，跑出数据再决定加不加投」
        反例：「做内容要有耐心」（这是废话，不要收）
- case  他讲的具体经历、数字、真实案例
- quote 能单独截图、能当结尾的一句话
- avoid 别做什么、踩过的坑
- qa    有人提问 + 他的回答，成对收

硬规则：
1. text 必须是原文里真实出现的字句，可以删语气词（啊/那个/就是说），**但不能改写意思、不能编**。
2. 口语里一段话讲完一个完整方法时，**合并成一条 dry**，不要把步骤拆成好几条碎句。
3. 同一块里同义重复的只留一条。
4. 一块最多出 6 条。没有合适的板块就不出，宁可少。
5. 纯寒暄、报时、求关注、念 ID、无意义语气词，全部丢掉。"""


def key():
    return open(KEYFILE, encoding="utf-8").read().strip()


def call(prompt, timeout=120):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1500,
    }).encode("utf-8")
    req = urllib.request.Request(GATEWAY, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key(),
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    c = j["choices"][0]["message"].get("content")
    if not c:
        raise RuntimeError("empty content")
    return c


def parse(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return []
    out = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        b = str(x.get("board", "")).strip().lower()
        t = str(x.get("text", "")).strip()
        n = str(x.get("note", "")).strip()
        if b in BOARDS and len(t) >= 6:
            out.append((b, t[:400], n[:40]))
    return out[:6]


def log(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def chunks_of(text):
    """按句子切，不硬切字。每块 <= CHUNK，块间留 OVERLAP 字重叠。"""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    sents = re.split(r"(?<=[。！？!?…])", text)
    out, buf = [], ""
    for s in sents:
        if len(buf) + len(s) <= CHUNK:
            buf += s
        else:
            if buf:
                out.append(buf)
            # 新块带上上一块尾巴，避免衔接处丢内容
            buf = (buf[-OVERLAP:] if buf else "") + s
    if buf:
        out.append(buf)
    return out


def ensure(conn):
    conn.execute("""create table if not exists post_split_done(
        post_id text, chunk_idx integer, items integer, at text,
        primary key(post_id, chunk_idx))""")
    conn.commit()


def todo(conn, kinds, limit=None):
    ph = ",".join("?" * len(kinds))
    rows = conn.execute(
        "select id, kind, text from posts where kind in (%s) and length(text) >= 200 order by date" % ph,
        tuple(kinds)).fetchall()
    jobs = []
    for pid, kind, text in rows:
        done = {r[0] for r in conn.execute(
            "select chunk_idx from post_split_done where post_id=?", (pid,))}
        for i, ch in enumerate(chunks_of(text)):
            if i in done:
                continue
            jobs.append((pid, kind, i, ch))
    if limit:
        jobs = jobs[:limit]
    return jobs


def work(job):
    pid, kind, idx, ch = job
    try:
        raw = call("稿件类型：%s\n\n正文：\n%s" % ("直播录音转写" if kind == "live" else "短视频口播转写", ch))
        return (pid, kind, idx, parse(raw), None)
    except Exception as e:
        return (pid, kind, idx, [], str(e)[:120])


def main():
    kind_arg = "live"
    if "--kind" in sys.argv:
        kind_arg = sys.argv[sys.argv.index("--kind") + 1]
    kinds = ["live", "douyin"] if kind_arg == "all" else [kind_arg]
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    conn = sqlite3.connect(DB, check_same_thread=False, timeout=90)
    # 书库那边有 96 路并发在写同一个库，这边必须等锁，不能直接报错
    try:
        conn.execute("pragma busy_timeout = 90000")
    except Exception:
        pass
    ensure(conn)
    jobs = todo(conn, kinds, limit)
    log("待拆 %d 块（来源 %s，模型 %s）" % (len(jobs), "+".join(kinds), MODEL))
    if not jobs:
        log("没有要拆的块")
        return

    ok = items_total = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=24) as ex:
        for i, (pid, kind, idx, items, err) in enumerate(ex.map(work, jobs), 1):
            if err:
                log("  失败 %s#%d: %s" % (pid[:18], idx, err))
                continue
            for k, (board, text, note) in enumerate(items):
                sid = "%s_%s_%03d_%03d" % (pid, board, idx, k)
                conn.execute(
                    "insert or replace into split_items(id,post_id,board,text,note,date,source,created_at)"
                    " values(?,?,?,?,?,?,?,datetime('now'))",
                    (sid, pid, board, text, note, time.strftime("%Y-%m-%d"), kind))
            conn.execute("insert or replace into post_split_done(post_id,chunk_idx,items,at)"
                         " values(?,?,?,datetime('now'))", (pid, idx, len(items)))
            items_total += len(items)
            ok += 1
            if i % 10 == 0:
                conn.commit()
                log("  进度 %d/%d 块，已出 %d 条，均 %.2fs/块"
                    % (i, len(jobs), items_total, (time.time() - t0) / i))
    conn.commit()
    conn.close()
    log("完成：处理 %d 块，产出 %d 条，用时 %.1f 分钟"
        % (ok, items_total, (time.time() - t0) / 60))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
