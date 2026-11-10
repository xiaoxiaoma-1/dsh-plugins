# -*- coding: utf-8 -*-
"""粗跑 200 本，收集话题词（不写库，只收集）。

目的：让模型从真实书里长出话题词，再归并成 20-40 个标准词。
上次 20 本试跑暴露：每本自己造新词，44 个词各出现 1 次 → 必须靠归并收口。
"""
import json
import random
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
OUT = r"E:\desktop\media\_topic_words_1000.json"
LOG = r"E:\desktop\media\topic_words.log"

SYS = """你在给一个内容创作者的书库打标签。他会说「我想写一篇关于 X 的内容」，系统要能靠标签把相关的书捞出来。

对每一本书，给出：
1. topic（话题）：这本书能让读者学到「关于什么的认知」。用 2-6 个字，要具体，不要用「商业」「心理」这种学科名。1-3 个。
   好例子：搞钱思路、带团队、原生家庭、看人识人、说话分寸
   坏例子：商业、心理、哲学（太泛）
2. kind（内容类型）：从观点类 / 方法类 / 案例类 / 数据类 里选 1-2 个。

只输出 JSON 数组，不要解释。格式：
[{"i":1,"topic":["搞钱思路"],"kind":["方法类"]}]"""


def key():
    return open(KEYFILE, encoding="utf-8").read().strip()


def call(prompt, timeout=180):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
        "temperature": 0.3, "max_tokens": 1200,
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
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        return []


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def work(item):
    i, title, head = item
    try:
        raw = call('第 1 本：《%s》\n   开头：%s' % (title[:40], head[:700]))
        cards = parse(raw)
        if cards:
            c = cards[0]
            return (i, title[:50], c.get("topic") or [], c.get("kind") or [], None)
        return (i, title[:50], [], [], "空返回")
    except Exception as e:
        return (i, title[:50], [], [], str(e)[:80])


def main():
    n = 1000
    conn = sqlite3.connect(DB, timeout=60)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "select id,title from books where id in (select distinct book_id from book_chunks)")]
    random.seed(20261105)
    sample = random.sample(rows, min(n, len(rows)))
    items = []
    for i, r in enumerate(sample, 1):
        ch = conn.execute("select content from book_chunks where book_id=? order by page_from limit 1",
                          (r['id'],)).fetchone()
        items.append((i, (r['title'] or ''), ((ch['content'] if ch else '') or '').replace('\n', ' ')))
    conn.close()

    log("开始粗跑 %d 本（模型 %s）" % (len(items), MODEL))
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=24) as ex:
        for k, res in enumerate(ex.map(work, items), 1):
            results.append(res)
            if k % 25 == 0:
                log("  进度 %d/%d，均 %.2fs" % (k, len(items), (time.time() - t0) / k))

    ok = [r for r in results if r[2]]
    log("完成：成功 %d / %d，用时 %.1f 分钟" % (len(ok), len(results), (time.time() - t0) / 60))

    cnt = Counter()
    for r in ok:
        for t in r[2]:
            cnt[t] += 1
    log("话题词共 %d 个" % len(cnt))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            'model': MODEL, 'total': len(results), 'ok': len(ok),
            'words': cnt.most_common(),
            'items': [{'title': r[1], 'topics': r[2], 'kinds': r[3]} for r in ok],
            'failed': [{'title': r[1], 'err': r[4]} for r in results if r[4]],
        }, f, ensure_ascii=False, indent=1)
    log("已写 " + OUT)


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
