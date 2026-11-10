# -*- coding: utf-8 -*-
"""打印看板统计 JSON（给 host 端 spawn 调用）。"""
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"E:\desktop\media\workbench.db"
STATUS = os.path.join(HERE, "status.json")
# status.json 由拆解进程自己写。进程被杀或崩掉时，文件会永远停在
# state=running，看板就一直显示"正在拆解 · 实时"。超过这个秒数没更新，
# 一律当作没有任务。
STALE_SEC = 600


def load_status():
    """返回 (status_dict, stale)。stale=True 表示这份状态已不可信。"""
    if not os.path.exists(STATUS):
        return {}, True
    try:
        st = json.load(open(STATUS, encoding="utf-8"))
    except Exception:
        return {}, True
    try:
        ts = os.path.getmtime(STATUS)
    except OSError:
        ts = 0
    return st, (time.time() - ts) > STALE_SEC


def one(c, sql):
    return c.execute(sql).fetchone()[0]


def main():
    c = sqlite3.connect(DB)
    try:
        boards = dict(c.execute("select board,count(*) from split_items group by board").fetchall())
        book_src = one(c, "select count(*) from split_items where source='book'")
        post_src = one(c, "select count(*) from split_items where source<>'book'")
        today = one(c, "select count(*) from split_items where date(created_at)=date('now')")
        done = one(c, "select count(*) from book_split_done")
        left = one(c, """select count(*) from book_chunks ch join books b on b.id=ch.book_id
                         where ch.id not in (select chunk_id from book_split_done)
                           and length(ch.content)>=120""")
        books = one(c, "select count(*) from books")
        cats = one(c, "select count(distinct category) from books where category<>''")
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
    # 状态过期 → 强制报 idle，别让看板一直说"正在拆解"
    state = "idle" if stale else st.get("state", "idle")
    out = {
        "ok": True,
        "boards": boards,
        "book_src": book_src, "post_src": post_src, "today": today,
        "done_chunks": done, "left": left, "total_chunks": done + left,
        "books": books, "cats": cats,
        "state": state,
        "statusStale": stale,
        "updated": st.get("updated", ""),
        "now": time.strftime("%H:%M:%S"),
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
