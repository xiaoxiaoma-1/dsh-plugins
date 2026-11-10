# -*- coding: utf-8 -*-
"""给未分类的书批量分类（用书卡摘要，不重读书）。

用法：python classify_rest.py --sample 10 / --go
"""
import argparse
import io
import json
import re
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

CATS = [
    "经济与金融", "财富与投资", "商业与经营", "商业与营销",
    "哲学与思想", "国学与心学", "历史与人物", "心理与认知",
    "科学与技术", "文学与艺术", "政治与制度", "社会与人文",
    "生活与健康", "职场与体制",
]

SYSTEM = """你是图书分类员。给你书名和内容摘要，从下面固定分类里选**一个**：

%s

只能从上面选，不许自创新分类，不许输出多个。
严格只输出 JSON：{"cat": "分类名", "why": "8字以内的依据"}""" % "\n".join("- " + x for x in CATS)


def call(title, gist):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": "书名：%s\n摘要：%s" % (title, gist)}],
        "temperature": 0.1, "max_tokens": 200,
    }).encode("utf-8")
    req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                 headers={"content-type": "application/json",
                                          "authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=120) as r:
        j = json.loads(r.read().decode("utf-8"))
    return (j["choices"][0]["message"]["content"] or "").strip()


def one(row):
    bid, title, gist = row
    try:
        raw = call(title, gist or "")
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return (bid, None, "解析失败")
        o = json.loads(m.group(0))
        cat = (o.get("cat") or "").strip()
        if cat not in CATS:
            # 容错：找最像的
            for c in CATS:
                if c in cat or cat in c:
                    cat = c
                    break
            else:
                return (bid, None, "分类不在列表: " + cat[:20])
        return (bid, (cat, o.get("why") or ""), None)
    except Exception as e:
        return (bid, None, str(e)[:80])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--conc", type=int, default=32)
    a = ap.parse_args()

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = c.execute("""select b.id, b.title, k.gist from books b
                        left join book_card k on k.book_id=b.id
                        where coalesce(b.category,'')='' or b.category='待定'
                        order by b.title""").fetchall()
    todo = [(r["id"], r["title"] or "", r["gist"] or "") for r in rows]
    print("待分类: %d 本" % len(todo))
    if a.sample:
        todo = todo[:a.sample]
        print("抽样 %d 本" % len(todo))
    if not a.go and not a.sample:
        print("加 --go 或 --sample N")
        return

    t0 = time.time()
    ok = fail = 0
    from collections import Counter
    dist = Counter()
    with ThreadPoolExecutor(max_workers=a.conc) as ex:
        futs = {ex.submit(one, r): r for r in todo}
        for i, f in enumerate(as_completed(futs), 1):
            bid, res, err = f.result()
            name = futs[f][1]
            if res:
                cat, why = res
                c.execute("update books set category=? where id=?", (cat, bid))
                dist[cat] += 1
                ok += 1
                if i <= 20 or i % 50 == 0:
                    print("[%d/%d] %-34s → %-8s (%s)" % (i, len(todo), name[:34], cat, why))
            else:
                fail += 1
                print("[%d/%d] ✗ %-30s %s" % (i, len(todo), name[:30], err))
            if i % 50 == 0:
                c.commit()
    c.commit()

    print("\n完成：成功 %d / 失败 %d / 用时 %.1f 分钟" % (ok, fail, (time.time() - t0) / 60))
    print("\n分类分布:")
    for k, v in dist.most_common():
        print("  %-12s %3d 本" % (k, v))
    print("\n现在全库分类:")
    for r in c.execute("select coalesce(nullif(category,''),'(空)') ct, count(*) n from books group by ct order by n desc"):
        print("  %-14s %3d" % (r["ct"][:14], r["n"]))
    c.close()


if __name__ == "__main__":
    main()
