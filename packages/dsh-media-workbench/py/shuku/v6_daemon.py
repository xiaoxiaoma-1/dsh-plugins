# -*- coding: utf-8 -*-
"""v6 全量守护进程：循环调用 extract_v2.py 直到没有剩余块。

停止：在 E:\\desktop\\书库盘点 下建 STOP_V6 文件。
状态：status_v6.json
"""
import json
import os
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
STOP = os.path.join(HERE, "STOP_V6")
STATUS = os.path.join(HERE, "status_v6.json")
LOG = os.path.join(HERE, "v6_daemon.log")
BATCH = 400
WORKERS = 48


def log(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def left():
    c = sqlite3.connect(r"E:\desktop\media\workbench.db", timeout=30)
    total = c.execute("select count(*) from book_chunks ch join books b on b.id=ch.book_id "
                      "where length(ch.content)>=200 and b.category not in ('冥想与身心','身心与养生','待定') "
                      "and b.title not like '%小说%'").fetchone()[0]
    done = c.execute("select count(*) from v6_done").fetchone()[0]
    c.close()
    return total - done


def write_status(state, n):
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({"state": state, "left": n, "updated": time.strftime("%Y-%m-%d %H:%M:%S")},
                  f, ensure_ascii=False)


def main():
    log("=== v6 daemon 启动 ===")
    c = sqlite3.connect(r"E:\desktop\media\workbench.db", timeout=60)
    c.execute("create table if not exists v6_done(chunk_id text primary key, at text)")
    c.commit()
    c.close()

    rounds = 0
    while True:
        if os.path.exists(STOP):
            write_status("paused", left())
            log("检测到 STOP_V6，暂停")
            return
        n = left()
        write_status("running", n)
        if n <= 0:
            write_status("idle", 0)
            log("全部拆完，退出")
            return
        rounds += 1
        t0 = time.time()
        r = subprocess.run([PY, os.path.join(HERE, "extract_v2.py"), str(BATCH), str(WORKERS)],
                           cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = (r.stdout or "").strip().splitlines()
        tail = out[-1] if out else (r.stderr or "")[-200:]
        log("第 %d 轮（剩 %d）：%s  用时 %.1f 分钟" % (rounds, n, tail, (time.time() - t0) / 60))
        if r.returncode != 0:
            log("本轮失败：" + (r.stderr or "")[-300:])
            time.sleep(30)
        time.sleep(2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
