# -*- coding: utf-8 -*-
"""拆解看板 · 独立窗口（读同一个 workbench.db + status.json，带启停按钮）。"""
import json
import os
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"E:\desktop\media\workbench.db"
STATUS = os.path.join(HERE, "status.json")
CTL = os.path.join(HERE, "split_ctl.py")
UI = os.path.join(HERE, "ui", "dashboard.html")
# status.json 由拆解进程写。进程被杀后它会永远停在 running，看板就会
# 一直显示"正在拆解"。超过这个秒数没更新，一律当作没有任务。
STALE_SEC = 600


def q(conn, sql):
    return conn.execute(sql).fetchone()[0]


def stats():
    c = sqlite3.connect(DB)
    try:
        boards = dict(c.execute("select board,count(*) from split_items group by board").fetchall())
        book_src = q(c, "select count(*) from split_items where source='book'")
        post_src = q(c, "select count(*) from split_items where source<>'book'")
        today = q(c, "select count(*) from split_items where date(created_at)=date('now')")
        done_chunks = q(c, "select count(*) from book_split_done")
        left = q(c, """select count(*) from book_chunks ch join books b on b.id=ch.book_id
                       where ch.id not in (select chunk_id from book_split_done)
                         and length(ch.content)>=120""")
        books = q(c, "select count(*) from books")
        cats = q(c, "select count(distinct category) from books where category<>''")
    finally:
        c.close()
    st = {}
    stale = True
    if os.path.exists(STATUS):
        try:
            st = json.load(open(STATUS, encoding="utf-8"))
        except Exception:
            st = {}
        try:
            stale = (time.time() - os.path.getmtime(STATUS)) > STALE_SEC
        except OSError:
            stale = True
    total_chunks = done_chunks + left
    return {
        "boards": boards,
        "book_src": book_src,
        "post_src": post_src,
        "today": today,
        "done_chunks": done_chunks,
        "left": left,
        "total_chunks": total_chunks,
        "books": books,
        "cats": cats,
        "state": "idle" if stale else st.get("state", "idle"),
        "statusStale": stale,
        "updated": st.get("updated", ""),
        "now": time.strftime("%H:%M:%S"),
    }


class Api:
    def stats(self):
        return stats()

    def _ctl(self, cmd):
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        r = subprocess.run([sys.executable, CTL, cmd], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=60)
        try:
            return json.loads((r.stdout or "{}").strip().splitlines()[-1])
        except Exception:
            return {"ok": False, "msg": (r.stdout or r.stderr or "")[-120:]}

    def start(self):
        j = self._ctl("start")
        j["stats"] = stats()
        return j

    def pause(self):
        j = self._ctl("pause")
        j["stats"] = stats()
        return j

    def cancel(self):
        j = self._ctl("cancel")
        j["stats"] = stats()
        return j


def main():
    import webview
    webview.create_window("拆解看板", UI, js_api=Api(),
                          width=1180, height=780, min_size=(900, 640),
                          background_color="#14161a")
    try:
        webview.start(gui="edgechromium", debug=False, private_mode=False)
    except Exception:
        webview.start(debug=False, private_mode=False)


if __name__ == "__main__":
    main()
