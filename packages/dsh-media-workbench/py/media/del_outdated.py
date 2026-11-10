# -*- coding: utf-8 -*-
"""删掉「内容严重过时」的书：先备份，再删记录+书块+文件。

用法：
  python del_outdated.py --dry    只看清单不动手
  python del_outdated.py --go     执行
"""
import argparse
import io
import json
import os
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"
LIB = r"E:\wengao"
MD = r"E:\wengao_md"
OCR = r"E:\wengao_ocr"

# 判定「过时 / 损坏 / 无内容」的书名关键词
KILL = [
    # ① 过时炒股书（9 本）
    "时机波动理论",
    "兆君：2010如何抓涨停板",
    "短线是银之四",
    "时空法则",
    "绝对涨停",
    "停板上金",
    "K线图定式图谱",
    "安道全周报",
    # ② 文件损坏（1 本，必须精确匹配——"官场权谋"会误伤长短经/民国官场权谋等 4 本好书）
    "官场权谋_邹纪孟著",
    # ③ 软件说明书 / 无内容（2 本）
    "网上交易闪电版",
    "玩赚你的网站",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    # 找书
    hits = []
    for kw in KILL:
        for r in c.execute("select id,title,pages,source_path from books where instr(title,?)>0", (kw,)):
            if any(h["id"] == r["id"] for h in hits):
                continue
            nch = c.execute("select count(*) from book_chunks where book_id=?", (r["id"],)).fetchone()[0]
            hits.append({"id": r["id"], "title": r["title"], "pages": r["pages"] or 0,
                         "path": r["source_path"] or "", "chunks": nch, "kw": kw})

    print("=" * 66)
    print("将删除 %d 本：" % len(hits))
    total_chunks = 0
    for h in hits:
        total_chunks += h["chunks"]
        print("  [%s] %-42s %4d页 %3d块" % (h["id"][:12], h["title"][:42], h["pages"], h["chunks"]))
        if h["path"]:
            print("        源文件: %s" % h["path"])
    print("  合计 %d 条书块" % total_chunks)

    if a.dry or not a.go:
        print("\n（dry 模式，没有动手。加 --go 执行）")
        return

    # 备份
    bak = r"E:\desktop\media\_deleted_outdated_%s.json" % time.strftime("%Y%m%d_%H%M%S")
    payload = {"books": [], "chunks": [], "files": []}
    for h in hits:
        br = c.execute("select * from books where id=?", (h["id"],)).fetchone()
        payload["books"].append(dict(br))
        for x in c.execute("select * from book_chunks where book_id=?", (h["id"],)):
            payload["chunks"].append(dict(x))
    with open(bak, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print("\n已备份: %s" % bak)
    print("  %d 本书 / %d 条书块" % (len(payload["books"]), len(payload["chunks"])))

    # 删
    for h in hits:
        c.execute("delete from book_chunks where book_id=?", (h["id"],))
        c.execute("delete from book_card where book_id=?", (h["id"],))
        try:
            c.execute("delete from book_quality where book_id=?", (h["id"],))
            c.execute("delete from book_classify where book_id=?", (h["id"],))
            c.execute("delete from book_labels where book_id=?", (h["id"],))
            c.execute("delete from book_metric where book_id=?", (h["id"],))
        except Exception:
            pass
        c.execute("delete from books where id=?", (h["id"],))
    c.commit()

    # 删文件
    # ★ 文件匹配只认精确相等。
    # 曾用 `stem in t` 导致 "28.md" 匹配到 "20160228安道全周报收费版"，
    # 把毛泽东选集第三卷等 5 个纯数字命名的 md 误删。
    # 判据：文件名（去扩展名）必须与书名完全相等，或书名以它开头且它长度 > 8。
    deleted = []
    titles = [h["title"] for h in hits]
    for d in (LIB, MD, OCR):
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            stem = os.path.splitext(name)[0]
            hit = False
            for t in titles:
                if stem == t:
                    hit = True
                    break
                if len(stem) > 8 and t.startswith(stem):
                    hit = True
                    break
            if not hit:
                continue
            p = os.path.join(d, name)
            try:
                os.remove(p)
                deleted.append(p)
                print("  删文件: %s" % name[:60])
            except Exception as e:
                print("  删不掉 %s: %s" % (name[:40], e))

    payload["files"] = deleted
    with open(bak, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print("\n完成：删 %d 本 / %d 条书块 / %d 个文件" % (len(hits), total_chunks, len(deleted)))
    print("书库现在: %d 本 / %d 块" % (
        c.execute("select count(*) from books").fetchone()[0],
        c.execute("select count(*) from book_chunks").fetchone()[0]))
    c.close()


if __name__ == "__main__":
    main()
