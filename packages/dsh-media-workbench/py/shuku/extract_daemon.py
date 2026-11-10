# -*- coding: utf-8 -*-
"""六板块拆解的长驻队列：一轮轮跑 extract_split，直到全部拆完。

停止：在 E:\\desktop\\书库盘点\\ 建 STOP_SPLIT 文件。
日志：extract_daemon.log
"""
import os
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"E:\desktop\media\workbench.db"
PY = sys.executable
STOP = os.path.join(HERE, "STOP_SPLIT")
LOG = os.path.join(HERE, "extract_daemon.log")


def log(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def remaining():
    c = sqlite3.connect(DB)
    n = c.execute("""select count(*) from book_chunks ch
                     join books b on b.id=ch.book_id
                     where ch.id not in (select chunk_id from book_split_done)
                       and length(ch.content)>=120""").fetchone()[0]
    c.close()
    return n


STATUS = os.path.join(HERE, "status.json")


def write_status(state, left, done=0, total=0, rate=0.0):
    import json
    try:
        json.dump({"state": state, "left": left, "done": done, "total": total,
                   "rate": round(rate, 1), "updated": time.strftime("%Y-%m-%d %H:%M:%S")},
                  open(STATUS, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


def main():
    log("=== 拆解 daemon 启动 ===")
    while True:
        if os.path.exists(STOP):
            write_status("paused", remaining())
            log("发现 STOP_SPLIT，退出")
            os.remove(STOP)
            return
        left = remaining()
        log("剩余待拆 %d 块" % left)
        write_status("running" if left > 0 else "idle", left)
        if left <= 0:
            write_status("idle", 0)
            log("全部拆完，退出")
            return
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        r = subprocess.run([PY, os.path.join(HERE, "extract_split.py"), "--limit", "400", "--apply"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        for line in out.splitlines()[-3:]:
            log("  " + line[:160])
        if r.returncode != 0:
            log("  本轮异常，歇 30 秒再试")
            time.sleep(30)
        time.sleep(2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
