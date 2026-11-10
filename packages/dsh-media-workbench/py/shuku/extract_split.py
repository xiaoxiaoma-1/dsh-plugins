# -*- coding: utf-8 -*-
"""书 → 六板块拆解（钩子/干货/案例/金句/避坑/问答），写进 split_items。

模型走本机 DSH 网关 http://127.0.0.1:8326/v1（OpenAI 兼容），不烧外部 key。
用法：
  python extract_split.py --limit 3            # 试 3 块，看质量
  python extract_split.py                      # 全量（断点续跑）
  python extract_split.py --books 100          # 只做前 100 本
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
LOG = r"E:\desktop\书库盘点\extract_split.log"

BOARDS = {"hook": "钩子", "dry": "干货", "case": "案例",
          "quote": "金句", "avoid": "避坑", "qa": "问答"}

SYS = """你是中文内容编辑。从给定的书籍段落里挑出可以放进短视频/文案的素材，按六个板块归类。
只输出 JSON 数组，不要任何解释、不要 markdown 代码块。
每个元素：{"board":"hook|dry|case|quote|avoid|qa","text":"原文里的一句或两三句原话，不改写","note":"不超过18字的提炼"}
规则：
- text 必须是原文里真实出现的字句，不许改写、不许编。
- 一段话最多出 4 条；没有合适的板块就不要硬凑，宁可少。
- hook＝能当开头第一句、抓人；dry＝道理/步骤/方法；case＝具体事例；quote＝能单独截图的一句话；avoid＝别做什么、坑；qa＝问题+答案。
- 纯标题、页眉页脚、目录、无意义的残句不要。"""


def key():
    return open(KEYFILE, encoding="utf-8").read().strip()


def call(prompt, timeout=120):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1200,
    }).encode("utf-8")
    req = urllib.request.Request(GATEWAY, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key(),
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    msg = j["choices"][0]["message"]
    c = msg.get("content")
    if not c:
        # 有的模型把内容都塞进 reasoning，重试一次
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
    return out[:4]


def log(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def ensure(conn):
    conn.execute("""create table if not exists book_split_done(
        chunk_id text primary key, items integer, at text)""")
    conn.commit()


def todo_chunks(conn, limit=None, books=None):
    q = """select c.id, c.book_id, c.content, b.title from book_chunks c
           join books b on b.id=c.book_id
           where c.id not in (select chunk_id from book_split_done)
             and length(c.content) >= 120"""
    if books:
        q += " and b.id in (select id from books order by id limit %d)" % books
    q += " order by c.book_id, c.page_from"
    if limit:
        q += " limit %d" % limit
    return conn.execute(q).fetchall()


def work(row):
    cid, bid, content, title = row
    try:
        raw = call("书名：《%s》\n\n段落：\n%s" % (title[:40], content[:1800]))
        items = parse(raw)
        return (cid, bid, title, items, None)
    except Exception as e:
        return (cid, bid, title, [], str(e)[:120])


def main():
    limit = None
    books = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    if "--books" in sys.argv:
        books = int(sys.argv[sys.argv.index("--books") + 1])
    apply = "--apply" in sys.argv

    conn = sqlite3.connect(DB, check_same_thread=False)
    ensure(conn)
    rows = todo_chunks(conn, limit, books)
    log("待拆 %d 块（模型 %s）" % (len(rows), MODEL))
    if not rows:
        return

    ok = items_total = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=96) as ex:
        for i, (cid, bid, title, items, err) in enumerate(ex.map(work, rows), 1):
            if err:
                log("  失败 %s: %s" % (title[:24], err))
                continue
            if items:
                for k, (board, text, note) in enumerate(items):
                    sid = "%s_%s_%03d" % (cid, board, k)
                    conn.execute(
                        "insert or replace into split_items(id,post_id,board,text,note,date,source,created_at)"
                        " values(?,?,?,?,?,?,?,datetime('now'))",
                        (sid, bid, board, text, note, time.strftime("%Y-%m-%d"), "book"))
                items_total += len(items)
            conn.execute("insert or replace into book_split_done(chunk_id,items,at) values(?,?,datetime('now'))",
                         (cid, len(items)))
            ok += 1
            if i % 20 == 0:
                conn.commit()
                log("  进度 %d/%d 块，已出 %d 条，均 %.2fs/块"
                    % (i, len(rows), items_total, (time.time() - t0) / i))
    conn.commit()
    conn.close()
    log("完成：处理 %d 块，产出 %d 条，用时 %.1f 分钟" % (ok, items_total, (time.time() - t0) / 60))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
