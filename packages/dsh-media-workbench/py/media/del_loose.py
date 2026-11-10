# -*- coding: utf-8 -*-
"""删「纯拼凑」+「干货不多」的书。先 dry 列清单。

判据：
 A. 判词明确说「拼凑」
 B. 判词说「但部分…有参考价值」「少数洞察」「可快速浏览」「抽看」「个别」—— 有干货但不多
白名单：明确是经典 / 一手经验 / 有体系的，一律不删
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

# 白名单：书名含这些词的，绝不删
KEEP = [
    "技术元素", "股票作手回忆录", "高敏感是种天赋", "佐藤可士和", "丑小鸭",
    "芒格", "创业时,我们在知乎聊什么", "世界商战权谋", "知日杂志", "微表情",
    "新管理哲学", "黄石公素书", "鬼谷子破局术", "权谋高手李鸿章", "证券交易之道",
    "石开投资经历的编辑", "转折生命力", "老A回忆录", "非理性繁荣", "大败局",
    "参与感", "增长黑客", "非同寻常的大众幻想", "周鸿祎", "实体店109套",
    "有效的广告创意", "创造性思维36计",
]

STRONG = ["拼凑"]
WEAK = ["但部分", "少数", "可快速浏览", "抽看", "可选择性阅读", "个别", "可选取",
        "按需", "快速浏览", "抽读", "选读"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    rows = c.execute("""select k.book_id, b.title, b.pages, k.verdict, k.gist, k.why
                        from book_card k join books b on b.id=k.book_id
                        where k.verdict='翻翻'""").fetchall()

    hits = []
    for r in rows:
        t = r["title"] or ""
        if any(k in t for k in KEEP):
            continue
        w = (r["why"] or "") + " " + (r["gist"] or "")
        if any(k in w for k in STRONG):
            hits.append((r, "拼凑"))
        elif any(k in w for k in WEAK):
            hits.append((r, "干货不多"))

    print("=" * 68)
    print("将删 %d 本（翻翻共 %d 本）" % (len(hits), len(rows)))
    print("\n【明确拼凑】%d 本" % len([1 for _, k in hits if k == "拼凑"]))
    for r, k in hits:
        if k == "拼凑":
            print("  %4s页 | %-32s | %s" % (r["pages"] or "?", (r["title"] or "")[:32], (r["why"] or "")[:40]))
    print("\n【有干货但不多】%d 本" % len([1 for _, k in hits if k == "干货不多"]))
    for r, k in hits:
        if k == "干货不多":
            print("  %4s页 | %-32s | %s" % (r["pages"] or "?", (r["title"] or "")[:32], (r["why"] or "")[:40]))

    if not a.go:
        print("\n（dry 模式。加 --go 执行）")
        return

    # 备份
    bak = r"E:\desktop\media\_deleted_loose_%s.json" % time.strftime("%Y%m%d_%H%M%S")
    payload = {"books": [], "chunks": [], "cards": []}
    ids = [r["book_id"] for r, _ in hits]
    for bid in ids:
        br = c.execute("select * from books where id=?", (bid,)).fetchone()
        if br:
            payload["books"].append(dict(br))
        for x in c.execute("select * from book_chunks where book_id=?", (bid,)):
            payload["chunks"].append(dict(x))
        for x in c.execute("select * from book_card where book_id=?", (bid,)):
            payload["cards"].append(dict(x))
    with open(bak, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print("\n已备份: %s" % bak)
    print("  %d 本书 / %d 条书块 / %d 张卡" % (len(payload["books"]), len(payload["chunks"]), len(payload["cards"])))

    # 删
    for bid in ids:
        c.execute("delete from book_chunks where book_id=?", (bid,))
        c.execute("delete from book_card where book_id=?", (bid,))
        for tb in ("book_quality", "book_classify", "book_labels", "book_metric", "book_topics"):
            try:
                c.execute("delete from %s where book_id=?" % tb, (bid,))
            except Exception:
                pass
        c.execute("delete from books where id=?", (bid,))
    c.commit()

    # 删文件（只认精确相等，不用 in 子串）
    deleted = []
    titles = [(r["title"] or "") for r, _ in hits]
    for d in (r"E:\wengao", r"E:\wengao_md", r"E:\wengao_ocr"):
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            stem = os.path.splitext(name)[0]
            hit = any(stem == t or (len(stem) > 8 and t.startswith(stem)) for t in titles)
            if not hit:
                continue
            try:
                os.remove(os.path.join(d, name))
                deleted.append(name)
            except Exception:
                pass
    payload["files"] = deleted
    with open(bak, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print("\n完成：删 %d 本 / %d 个文件" % (len(ids), len(deleted)))
    print("书库: %d 本 / %d 块 / %d 张卡" % (
        c.execute("select count(*) from books").fetchone()[0],
        c.execute("select count(*) from book_chunks").fetchone()[0],
        c.execute("select count(*) from book_card").fetchone()[0]))
    c.close()


if __name__ == "__main__":
    main()
