# -*- coding: utf-8 -*-
"""压测：并发拉高，看速率是否线性上涨（判定瓶颈是单次延迟还是 TPM 限流）。"""
import json
import sqlite3
import sys
import threading
import time
import urllib.request

sys.path.insert(0, r"E:\desktop\书库盘点")
import extract_split as E

DB = E.DB
N_THREADS = int(sys.argv[1]) if len(sys.argv) > 1 else 24
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 45

conn = sqlite3.connect(DB)
rows = conn.execute(
    "select b.title, ch.content from book_chunks ch join books b on b.id=ch.book_id "
    "where length(ch.content)>200 limit 200").fetchall()
conn.close()

lock = threading.Lock()
stat = {"ok": 0, "err": 0, "tokens": 0, "status": {}}
idx = [0]


def worker():
    while True:
        with lock:
            if idx[0] >= len(rows) or time.time() > deadline:
                return
            i = idx[0]
            idx[0] += 1
        title, content = rows[i]
        body = json.dumps({
            "model": E.MODEL,
            "messages": [{"role": "system", "content": E.SYS},
                         {"role": "user", "content": "书名：《%s》\n\n段落：\n%s" % (title[:40], content[:1500])}],
            "temperature": 0.2, "max_tokens": 1200,
        }).encode("utf-8")
        req = urllib.request.Request(E.GATEWAY, data=body, headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + E.key()})
        try:
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.loads(r.read().decode("utf-8"))
            with lock:
                stat["ok"] += 1
                stat["tokens"] += (j.get("usage") or {}).get("total_tokens", 0)
                stat["status"]["200"] = stat["status"].get("200", 0) + 1
            print("  %.1fs ok" % (time.time() - t0), flush=True)
        except Exception as e:
            with lock:
                stat["err"] += 1
                code = getattr(e, "code", "x")
                stat["status"][code] = stat["status"].get(code, 0) + 1


deadline = time.time() + DURATION
t0 = time.time()
ths = [threading.Thread(target=worker, daemon=True) for _ in range(N_THREADS)]
for t in ths:
    t.start()
for t in ths:
    t.join(timeout=DURATION + 30)
el = time.time() - t0
print("\n并发 %d / %.0f 秒：成功 %d，失败 %d，速率 %.1f 块/分，%d tokens"
      % (N_THREADS, el, stat["ok"], stat["err"], stat["ok"] / el * 60, stat["tokens"]))
print("错误码分布：", stat["status"])
