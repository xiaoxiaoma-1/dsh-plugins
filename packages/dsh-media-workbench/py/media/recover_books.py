# -*- coding: utf-8 -*-
"""认书：把「书名只剩数字」的记录，从正文里认出它属于哪本书，然后按书归组。

背景：导入时按章节切分，一章存成一条 books 记录，标题只剩「01」「02」「7」。
正文开头往往重复出现书名（比如「老A处长教你混官场」），靠这个归组。
"""
import json
import re
import sqlite3
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DB = r"E:\desktop\media\workbench.db"
GATEWAY = "http://127.0.0.1:8326/v1/chat/completions"
KEYFILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
OUT = r"E:\desktop\media\_book_recover.json"

SYS = """我给你一段从书里截出来的正文开头，这本书的标题在导入时丢了，只剩编号。

请从正文里认出这是哪本书，输出书名。
- 书名通常会在开头重复出现（作者名、出版信息、章节标题附近）。
- 认不出就输出空字符串，不要猜。
- 只输出 JSON：{"book":"书名","conf":0.9}
conf 是你有多确定，0-1。不要解释。"""


def key():
    return open(KEYFILE, encoding="utf-8").read().strip()


def call(prompt, timeout=90):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
        "temperature": 0.1, "max_tokens": 120,
    }).encode("utf-8")
    req = urllib.request.Request(GATEWAY, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    return j["choices"][0]["message"].get("content") or ""


def parse(raw):
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return "", 0
    try:
        o = json.loads(m.group(0))
        return str(o.get("book") or "").strip()[:40], float(o.get("conf") or 0)
    except Exception:
        return "", 0


def work(item):
    bid, title, head = item
    try:
        book, conf = parse(call("编号：%s\n\n正文开头：\n%s" % (title, head[:600])))
        return (bid, title, book, conf)
    except Exception:
        return (bid, title, "", 0)


def main():
    conn = sqlite3.connect(DB, timeout=120)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("select id,title from books")]
    frag = [r for r in rows if re.fullmatch(r"[\d\s\W]{1,12}", (r['title'] or '').strip())]
    print("数字标题 %d 条，开始认书…" % len(frag))

    items = []
    for r in frag:
        ch = conn.execute("select content from book_chunks where book_id=? order by page_from limit 1",
                          (r['id'],)).fetchone()
        items.append((r['id'], r['title'], ((ch['content'] if ch else '') or '').replace('\n', ' ')))

    t0 = time.time()
    res = []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for k, r in enumerate(ex.map(work, items), 1):
            res.append(r)
            if k % 40 == 0:
                print("  进度 %d/%d，%.1f 分钟" % (k, len(items), (time.time() - t0) / 60))

    groups = {}
    unknown = []
    for bid, title, book, conf in res:
        if book and conf >= 0.6:
            groups.setdefault(book, []).append({'id': bid, 'title': title, 'conf': conf})
        else:
            unknown.append({'id': bid, 'title': title, 'guess': book, 'conf': conf})

    print("\n=== 认出 %d 本书 ===" % len(groups))
    for book, ms in sorted(groups.items(), key=lambda x: -len(x[1])):
        print("  《%s》→ %d 章：%s" % (book, len(ms), " / ".join(m['title'] for m in ms[:8])))
    print("\n=== 认不出 %d 条 ===" % len(unknown))
    for u in unknown[:12]:
        print("  ", u['title'], "| 猜:", u['guess'] or '—')

    json.dump({'groups': groups, 'unknown': unknown},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print("\n已写", OUT)


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
