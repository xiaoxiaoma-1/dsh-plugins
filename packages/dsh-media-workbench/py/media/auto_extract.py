# -*- coding: utf-8 -*-
"""观点自动提炼守护：每 5 分钟扫一次稿库和直播，有新转写内容就自动提炼成观点。

设计：
- 不改 capture_one.py / pipeline.py，谁入库都能被它捞到（守护式，不依赖调用方）
- 实际干的活交给 extract_views.py（断点续跑，已处理的自动跳过）
- 没新内容就静默等着，不刷日志
- 有进度就推悬浮球

用法（开机自启，用 pythonw 跑，不弹黑框）：
  pythonw.exe auto_extract.py
"""
import io
import os
import sqlite3
import subprocess
import sys
import time

DB = r"E:\desktop\media\workbench.db"
SCRIPT = r"E:\desktop\media\extract_views.py"
LOG = r"E:\desktop\media\_auto_extract.log"
PY = sys.executable
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
INTERVAL = 300  # 5 分钟扫一次

if sys.stdout is None or sys.stderr is None:
    _n = open(os.devnull, "w")
    sys.stdout = sys.stdout or _n
    sys.stderr = sys.stderr or _n
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def pending():
    """返回 (稿库待提炼数, 直播待提炼数)"""
    try:
        c = sqlite3.connect(DB, timeout=20)
        done = set()
        for (sid,) in c.execute("select src_id from atoms where src_id is not null"):
            p = str(sid).split(":")
            if len(p) >= 2:
                done.add(p[0] + ":" + p[1])
        n_post = 0
        for (pid,) in c.execute("select id from posts where text is not null and length(text)>200"):
            if "posts:" + str(pid) not in done:
                n_post += 1
        n_live = 0
        for (lid,) in c.execute("select id from live_segments where text is not null and length(text)>200"):
            if "live:" + str(lid) not in done:
                n_live += 1
        c.close()
        return n_post, n_live
    except Exception as e:
        log("扫库出错: %s" % e)
        return 0, 0


def run(src, conc):
    try:
        r = subprocess.run([PY, SCRIPT, "--src", src, "--limit", "0", "--conc", str(conc)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", creationflags=NOWIN, timeout=7200)
        tail = (r.stdout or "").strip().splitlines()
        log("[%s] %s" % (src, tail[-1] if tail else "(无输出)"))
    except Exception as e:
        log("[%s] 跑失败: %s" % (src, e))


def once():
    """扫一次就退出。DSH 启动时由插件调这个。"""
    n_post, n_live = pending()
    if not (n_post or n_live):
        return
    log("发现新内容：稿库 %d 篇 / 直播 %d 篇" % (n_post, n_live))
    if n_post:
        run("posts", 16)
    if n_live:
        run("live", 12)


def main():
    if "--once" in sys.argv:
        once()
        return
    # 兼容：不加 --once 就是老的常驻循环（一般不用）
    log("=== 自动提炼守护启动（每 %d 秒扫一次）===" % INTERVAL)
    while True:
        try:
            once()
        except Exception as e:
            log("循环出错: %s" % e)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
