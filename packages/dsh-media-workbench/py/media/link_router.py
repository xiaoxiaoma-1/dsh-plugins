# -*- coding: utf-8 -*-
"""链接分诊：判断是主页 / 视频 / 直播间，主页写入直播监控表。

用法：python link_router.py "<url>"
输出 JSON：{ok, kind, label, url, note}
"""
import json
import re
import sqlite3
import sys
import time

DB = r"E:\desktop\media\workbench.db"


def norm(u):
    u = (u or "").strip()
    # 从分享文案里抠链接
    m = re.search(r"https?://[^\s\u4e00-\u9fa5]+", u)
    return (m.group(0) if m else u).rstrip("，。,.、）)")


def classify(u):
    t = u.lower()
    if not u:
        return "empty", "空链接"
    if "live.douyin.com/" in t:
        return "live", "直播间（正在播）"
    if re.search(r"douyin\.com/(user|share/user)/", t):
        return "profile", "主页（等开播自动录）"
    if re.search(r"douyin\.com/(video|note)/", t) or "v.douyin.com/" in t:
        return "video", "视频（进文案采集）"
    if "xiaohongshu.com" in t or "xhslink.com" in t:
        return "video", "小红书（进文案采集）"
    if "bilibili.com/video" in t or "b23.tv" in t:
        return "video", "B站视频（进文案采集）"
    if re.search(r"douyin\.com/(share/)?live", t):
        return "live", "直播间"
    return "unknown", "认不出，按视频处理"


def ensure(c):
    c.execute("""create table if not exists live_watch(
        url text primary key, platform text, label text, note text,
        added_at text, last_check text)""")


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else ""

    # --list：列出已加入监控的主播
    if raw == "--list":
        c = sqlite3.connect(DB, timeout=30)
        ensure(c)
        rows = c.execute("select url,label,added_at from live_watch order by added_at desc").fetchall()
        c.close()
        print(json.dumps({"ok": True, "items": [
            {"url": r[0], "label": r[1], "added": r[2]} for r in rows]}, ensure_ascii=False))
        return

    url = norm(raw)
    kind, label = classify(url)
    out = {"ok": True, "kind": kind, "label": label, "url": url}

    if kind == "profile":
        c = sqlite3.connect(DB, timeout=30)
        ensure(c)
        c.execute("insert or ignore into live_watch values(?,?,?,?,?,?)",
                  (url, "douyin", label, "", time.strftime("%Y-%m-%d %H:%M:%S"), ""))
        c.commit()
        n = c.execute("select count(*) from live_watch").fetchone()[0]
        c.close()
        out["saved"] = True
        out["total_watch"] = n
        out["message"] = "已加入直播监控，共 %d 个主播" % n
    elif kind == "video":
        out["message"] = "进文案采集队列"
    elif kind == "live":
        out["message"] = "这是正在播的直播间，录制功能待接"
    else:
        out["message"] = label

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
