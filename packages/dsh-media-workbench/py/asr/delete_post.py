# -*- coding: utf-8 -*-
"""删除指定 post（先备份到 out/deleted/ 再删）"""
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB = r"E:\desktop\media\workbench.db"
OUT = r"E:\tools\asr\out"
BAK = os.path.join(OUT, "deleted")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pid = sys.argv[1] if len(sys.argv) > 1 else ""
    if not pid:
        print(json.dumps({"ok": False, "error": "missing post id"}, ensure_ascii=False))
        return

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    post = con.execute("SELECT * FROM posts WHERE id = ?", (pid,)).fetchone()
    src = None
    try:
        src = con.execute("SELECT * FROM post_sources WHERE post_id = ?", (pid,)).fetchone()
    except Exception:
        pass

    if not post:
        print(json.dumps({"ok": False, "error": "not found: " + pid}, ensure_ascii=False))
        con.close()
        return

    os.makedirs(BAK, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dump = {
        "deleted_at": datetime.now().isoformat(timespec="seconds"),
        "post": dict(post),
        "source": dict(src) if src else None,
    }
    bakfile = os.path.join(BAK, f"{pid}-{stamp}.json")
    with open(bakfile, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2)

    # 挪走音频/文本文件
    moved = []
    if src and src["vid"]:
        for ext in (".m4a", ".wav", ".txt", ".srt", ".json"):
            p = os.path.join(OUT, src["vid"] + ext)
            if os.path.exists(p):
                dst = os.path.join(BAK, os.path.basename(p))
                try:
                    shutil.move(p, dst)
                    moved.append(os.path.basename(p))
                except Exception:
                    pass

    con.execute("DELETE FROM posts WHERE id = ?", (pid,))
    try:
        con.execute("DELETE FROM post_sources WHERE post_id = ?", (pid,))
    except Exception:
        pass
    con.commit()
    left = con.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    con.close()

    print(json.dumps({
        "ok": True,
        "deleted": pid,
        "title": post["author"],
        "backup": bakfile,
        "moved_files": moved,
        "posts_left": left,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
