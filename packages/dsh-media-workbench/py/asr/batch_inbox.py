# -*- coding: utf-8 -*-
"""把私信抓取结果里还没进稿库的视频逐条转写入库。

跑法（后台）：pythonw batch_inbox.py
日志：E:\\tools\\asr\\out\\_batch_inbox.log
"""
import json
import os
import sqlite3
import subprocess
import sys
import time

PY = sys.executable
CAPTURE = r"E:\tools\asr\capture_one.py"
INBOX = r"E:\tools\asr\out\douyin_inbox_deep.json"
LOG = r"E:\tools\asr\out\_batch_inbox.log"
DB = r"E:\desktop\media\workbench.db"

if sys.stdout is None or sys.stderr is None:
    _n = open(os.devnull, "w")
    sys.stdout = sys.stdout or _n
    sys.stderr = sys.stderr or _n
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        print(line, flush=True)
    except Exception:
        pass


def processed_ids():
    """库里已有的 douyin 视频 id 集合"""
    ids = set()
    if not os.path.exists(DB):
        return ids
    c = sqlite3.connect(DB)
    try:
        for (pid,) in c.execute("select id from posts where kind='douyin'"):
            p = str(pid)
            if p.startswith("dy_"):
                ids.add(p[3:])
    except Exception:
        pass
    finally:
        c.close()
    return ids


def main():
    inbox = json.load(open(INBOX, encoding="utf-8"))
    items = inbox.get("items") or []
    have = processed_ids()
    todo = []
    skipped_bad = 0
    for it in items:
        vid = str(it.get("itemId") or "").strip()
        if not vid:
            continue
        t = (it.get("text") or "")
        if "无法查看" in t:      # 作者已删/失效
            skipped_bad += 1
            continue
        if vid in have:
            continue
        todo.append(vid)
    log(f"私信共 {len(items)} 条，库里已有 {len(have)} 条，失效跳过 {skipped_bad}，待转写 {len(todo)}")
    ok = fail = 0
    for i, vid in enumerate(todo, 1):
        url = "https://www.douyin.com/video/" + vid
        log(f"[{i}/{len(todo)}] 开始 {vid}")
        try:
            r = subprocess.run([PY, CAPTURE, url], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", creationflags=NOWIN, timeout=1800)
            tail = (r.stdout or "").strip().splitlines()
            last = tail[-1] if tail else (r.stderr or "")[-200:]
            if '"ok":true' in last.replace(" ", ""):
                ok += 1
                log(f"[{i}/{len(todo)}] 完成 {vid} -> {last[:160]}")
            else:
                fail += 1
                log(f"[{i}/{len(todo)}] 失败 {vid} -> {last[:240]}")
        except Exception as e:
            fail += 1
            log(f"[{i}/{len(todo)}] 异常 {vid} -> {e}")
    log(f"全部结束：成功 {ok}，失败 {fail}")


if __name__ == "__main__":
    main()
