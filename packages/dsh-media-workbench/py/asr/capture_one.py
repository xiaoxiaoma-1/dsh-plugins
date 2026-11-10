# -*- coding: utf-8 -*-
"""单条抖音链接 → 逐字稿 → 入库。

流程：
  node fetch.mjs <url>      抓音频（.m4a）
  ffmpeg                    转 16k 单声道 wav
  transcribe.py             Whisper GPU 转写（txt/srt/json）
  写 posts 表               带来源平台、作者、时长、原文链接

用法：python capture_one.py <douyin-url>
输出最后一行是 JSON：{"ok":true,"post_id":"...","title":"...","chars":1234}
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime

DB = r"E:\desktop\media\workbench.db"
NODE = r"G:\nj\node.exe"
FETCH = r"E:\tools\asr\node\fetch.mjs"
OUT = r"E:\tools\asr\out"
PY = sys.executable
TRANSCRIBE = r"E:\tools\asr\transcribe.py"
CLASSIFY = r"E:\tools\asr\classify.py"

CREATE_NO_WINDOW = 0x08000000
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "capture.log")


def log(msg):
    line = "[%s] %s" % (datetime.now().strftime("%m-%d %H:%M:%S"), msg)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run(cmd, timeout, cwd=None):
    p = subprocess.run(
        cmd, capture_output=True, timeout=timeout, cwd=cwd,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    out = (p.stdout or b"").decode("utf-8", errors="replace")
    err = (p.stderr or b"").decode("utf-8", errors="replace")
    return p.returncode, out, err


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "missing url"}, ensure_ascii=False))
        return
    url = sys.argv[1].strip()
    log("START " + url)

    # 1. 抓音频
    code, out, err = run([NODE, FETCH, url], timeout=300)
    if code != 0:
        log("FAIL fetch %s :: %s" % (url, (err or out)[-200:].replace("\n", " ")))
        print(json.dumps({"ok": False, "step": "fetch", "error": (err or out)[-400:]}, ensure_ascii=False))
        return
    vid = None
    for line in out.splitlines():
        m = re.search(r"\[vid\]\s*(\d+)", line)
        if m:
            vid = m.group(1)
    title = ""
    for line in out.splitlines():
        m = re.search(r"\[title\]\s*(.+)", line)
        if m:
            title = m.group(1).replace(" - 抖音", "").strip()
    if not vid:
        log("FAIL fetch no vid " + url)
        print(json.dumps({"ok": False, "step": "fetch", "error": "no vid"}, ensure_ascii=False))
        return

    # 查重：同一条视频（dy_<vid>）已经入库就直接跳过，不再转写
    try:
        con0 = sqlite3.connect(DB)
        row = con0.execute("SELECT id, length(text) FROM posts WHERE id=?", ("dy_" + vid,)).fetchone()
        con0.close()
        if row:
            log("DUP %s -> %s" % (vid, row[0]))
            print(json.dumps({
                "ok": True, "duplicate": True, "post_id": row[0], "chars": row[1] or 0,
                "title": title, "duration": 0,
            }, ensure_ascii=False))
            return
    except Exception:
        pass

    m4a = os.path.join(OUT, f"{vid}.m4a")
    wav = os.path.join(OUT, f"{vid}.wav")
    txt = os.path.join(OUT, f"{vid}.txt")
    if not os.path.exists(m4a):
        log("FAIL fetch m4a missing %s" % vid)
        print(json.dumps({"ok": False, "step": "fetch", "error": "m4a missing"}, ensure_ascii=False))
        return

    # 2. 转 wav（m4a 比 wav 新就重转，避免复用旧缓存）
    if os.path.exists(wav) and os.path.getmtime(wav) < os.path.getmtime(m4a):
        try:
            os.remove(wav)
        except OSError:
            pass
    # 空的 txt 不能当缓存（以前会拿 0 字节 txt 直接入库，判成"已完成"）
    if os.path.exists(txt) and os.path.getsize(txt) < 20:
        for ext in ('.txt', '.srt', '.json'):
            try:
                os.remove(os.path.join(OUT, vid + ext))
            except OSError:
                pass
    if not os.path.exists(wav):
        code, out, err = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                              "-i", m4a, "-vn", "-ac", "1", "-ar", "16000",
                              "-c:a", "pcm_s16le", wav], timeout=300)
        if code != 0 or not os.path.exists(wav):
            log("FAIL ffmpeg %s :: %s" % (vid, (err or out)[-200:].replace("\n", " ")))
            print(json.dumps({"ok": False, "step": "ffmpeg", "error": (err or out)[-300:]}, ensure_ascii=False))
            return

    # 3. 转写
    # 优先走常驻语音服务（8777）：它已经把模型装在内存里，复用它不额外吃内存。
    # 走本进程新加载模型时，若口播服务已占 5G+，mkl_malloc 会直接失败。
    if not os.path.exists(txt):
        done = False
        try:
            import urllib.request
            body = json.dumps({"wav": wav, "m": "turbo"}).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:8777/transcribe", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3600) as resp:
                j = json.loads(resp.read().decode("utf-8", errors="replace"))
            if j.get("ok") and (j.get("text") or "").strip():
                with open(txt, "w", encoding="utf-8") as f:
                    f.write(j["text"].strip())
                done = True
                print("[asr] 服务转写完成 %.1fs 音频" % (j.get("duration") or 0), flush=True)
        except Exception as e:
            print("[asr] 服务不可用，回退本地: %s" % str(e)[:120], flush=True)

        if not done:
            code, out, err = run([PY, TRANSCRIBE, wav], timeout=1800)
            if not os.path.exists(txt):
                print(json.dumps({"ok": False, "step": "asr", "error": (err or out)[-400:]}, ensure_ascii=False))
                return

    # 兜底：转写结果为空就本地重试一次，还空才判失败（之前 0 字节 txt 会被当成完成）
    if (not os.path.exists(txt)) or os.path.getsize(txt) < 20:
        log("empty transcript, retry local %s" % vid)
        try:
            os.remove(txt)
        except OSError:
            pass
        code, out, err = run([PY, TRANSCRIBE, wav], timeout=1800)
    if (not os.path.exists(txt)) or os.path.getsize(txt) < 20:
        log("FAIL asr empty %s" % vid)
        print(json.dumps({"ok": False, "step": "asr", "error": "empty transcript after retry"}, ensure_ascii=False))
        return

    with open(txt, "r", encoding="utf-8") as f:
        body = f.read().strip()
    if not body:
        print(json.dumps({"ok": False, "step": "asr", "error": "empty transcript"}, ensure_ascii=False))
        return

    # 4. 入库（posts 表）
    pid = "dy_" + vid
    now = datetime.now().isoformat(timespec="seconds")
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS posts (
          id TEXT PRIMARY KEY, author TEXT DEFAULT 'douyin', date TEXT, kind TEXT,
          text TEXT NOT NULL, url TEXT, created_at TEXT
        )
    """)
    con.execute(
        "INSERT OR REPLACE INTO posts (id, author, date, kind, text, url, created_at) VALUES (?,?,?,?,?,?,?)",
        (pid, (title[:40] if title else "抖音"), datetime.now().strftime("%Y-%m-%d"), "douyin", body, url, now),
    )
    # 附一张来源表，记平台/标题/时长，方便稿库分类
    con.execute("""
        CREATE TABLE IF NOT EXISTS post_sources (
          post_id TEXT PRIMARY KEY, platform TEXT, title TEXT, vid TEXT,
          duration REAL, audio_path TEXT, created_at TEXT
        )
    """)
    dur = 0.0
    try:
        jp = os.path.join(OUT, f"{vid}.json")
        if os.path.exists(jp):
            import json as _j
            dur = float(_j.load(open(jp, encoding="utf-8")).get("duration") or 0)
    except Exception:
        pass
    con.execute(
        "INSERT OR REPLACE INTO post_sources (post_id, platform, title, vid, duration, audio_path, created_at) VALUES (?,?,?,?,?,?,?)",
        (pid, "douyin", title, vid, dur, m4a, now),
    )
    con.commit()
    con.close()
    log("OK %s chars=%d title=%s" % (vid, len(body), (title or "")[:30]))

    # 入库后自动归类（关键词），避免新内容堆在「未分类」
    try:
        run([PY, CLASSIFY], timeout=60)
    except Exception:
        pass

    print(json.dumps({
        "ok": True, "post_id": pid, "vid": vid, "title": title,
        "chars": len(body), "duration": dur,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

