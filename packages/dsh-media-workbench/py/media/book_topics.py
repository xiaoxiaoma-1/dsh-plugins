# -*- coding: utf-8 -*-
"""给全部书打话题标签（从固定词表里选，不再发散）。

词表来源：1000 本粗跑 + 归并出的 19 个话题（_topic_merged_1000.json）。
写入新表 book_topics(book_id, topic, confidence)。
"""
import json
import re
import sqlite3
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

DB = r"E:\desktop\media\workbench.db"
GATEWAY = "http://127.0.0.1:8326/v1/chat/completions"
KEYFILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
WORDS = r"E:\desktop\media\_topic_merged_1000.json"
LOG = r"E:\desktop\media\book_topics.log"

merged = json.load(open(WORDS, encoding="utf-8"))
TOPICS = [x["topic"] for x in merged]
print("词表 %d 个话题: %s" % (len(TOPICS), " / ".join(TOPICS)))

SYS = """你在给一个内容创作者的书打话题标签。他会说「我想写一篇关于 X 的内容」，系统要能靠标签把相关的书捞出来。

【只能用下面这个词表，不许自己造新词】
%s

规则：
- 每本书选 1-3 个话题，按相关度从高到低。
- 选不出来就返回空数组，不要硬凑。
- 只输出 JSON：{"topics":["职场生存与晋升"],"why":"一句话"}
不要解释，不要 markdown。""" % "\n".join("- " + t for t in TOPICS)


def key():
    return open(KEYFILE, encoding="utf-8").read().strip()


def call(prompt, timeout=120):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
        "temperature": 0.2, "max_tokens": 200,
    }).encode("utf-8")
    req = urllib.request.Request(GATEWAY, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    c = j["choices"][0]["message"].get("content")
    if not c:
        raise RuntimeError("empty")
    return c


def parse(raw):
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return []
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return []
    ts = obj.get("topics") or []
    return [t for t in ts if t in TOPICS][:3]


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def work(item):
    bid, title, head = item
    try:
        raw = call("书名：《%s》\n开头：%s" % (title[:40], head[:700]))
        return (bid, title[:40], parse(raw), None)
    except Exception as e:
        return (bid, title[:40], [], str(e)[:80])


def main():
    conn = sqlite3.connect(DB, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma busy_timeout = 120000")
    conn.execute("""create table if not exists book_topics(
        book_id text, topic text, at text, primary key(book_id, topic))""")
    conn.commit()

    rows = [dict(r) for r in conn.execute(
        "select id,title from books where id in (select distinct book_id from book_chunks)")]
    done = {r[0] for r in conn.execute("select distinct book_id from book_topics")}
    todo = [r for r in rows if r['id'] not in done]
    log("待标 %d 本（已有 %d 本标过）" % (len(todo), len(done)))
    if not todo:
        return

    items = []
    for r in todo:
        ch = conn.execute("select content from book_chunks where book_id=? order by page_from limit 1",
                          (r['id'],)).fetchone()
        items.append((r['id'], r['title'] or '', ((ch['content'] if ch else '') or '').replace('\n', ' ')))

    t0 = time.time()
    ok = 0
    stats = Counter()
    with ThreadPoolExecutor(max_workers=24) as ex:
        for k, (bid, title, topics, err) in enumerate(ex.map(work, items), 1):
            if err:
                continue
            for t in topics:
                conn.execute("insert or replace into book_topics(book_id,topic,at) values(?,?,datetime('now'))",
                             (bid, t))
                stats[t] += 1
            ok += 1
            if k % 100 == 0:
                conn.commit()
                log("  进度 %d/%d，均 %.2fs" % (k, len(items), (time.time() - t0) / k))
    conn.commit()
    log("完成：标了 %d 本，用时 %.1f 分钟" % (ok, (time.time() - t0) / 60))

    print("\n=== 话题分布（实际书数，不是估算）===")
    for t, n in stats.most_common():
        print("  %-14s %d 本" % (t, n))
    conn.close()


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
