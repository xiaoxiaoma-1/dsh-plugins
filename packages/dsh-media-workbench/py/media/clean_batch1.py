# -*- coding: utf-8 -*-
"""第一批清理：小说 + 乱码碎片 + 付费文章/老A + 毛泽东全集
流程：备份 db → 导出待删正文到 JSON（可恢复）→ 删库记录 → 校验
"""
import json
import os
import re
import shutil
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BAK_DIR = r"E:\desktop\书库盘点\_清理备份_20261107_批1"
os.makedirs(BAK_DIR, exist_ok=True)

c = sqlite3.connect(DB)
d = json.load(open(r"E:\desktop\media\_quality_tier.json", encoding="utf-8"))


def info(bid):
    r = c.execute("select title from books where id=?", (bid,)).fetchone()
    n = c.execute("select coalesce(sum(length(content)),0) from book_chunks where book_id=?", (bid,)).fetchone()[0]
    return (r[0] if r else "?"), n


NOVEL = re.compile(r"(小说|叙事|情节|文学|散文|诗歌|诗集|玄幻|言情|穿越|晋江|琅琊榜|上册|下册|共\d册|三部曲|传奇)")
GARBAGE = re.compile(r"(乱码|符号|无有效|拼凑|跳跃|重复|图片|碎片|不连续|扫描|广告|招商)")

plan = {"小说": [], "乱码碎片": [], "付费文章/老A": [], "毛泽东全集": []}
for bid, v in d.items():
    t, n = info(bid)
    why = v.get("why") or ""
    if re.match(r"^毛泽东全集", t.strip()) or ("毛泽东全集" in t and re.search(r"第\d+卷", t) and "选集" not in t):
        plan["毛泽东全集"].append((bid, t, n, v.get("tier"), v.get("score")))
        continue
    if v.get("tier") != "C":
        continue
    if "付费文章" in t or "老A" in t:
        plan["付费文章/老A"].append((bid, t, n, v.get("tier"), v.get("score")))
    elif NOVEL.search(t + why):
        plan["小说"].append((bid, t, n, v.get("tier"), v.get("score")))
    elif GARBAGE.search(why):
        plan["乱码碎片"].append((bid, t, n, v.get("tier"), v.get("score")))

allids = sorted({bid for rows in plan.values() for bid, _, _, _, _ in rows})
print("待删 %d 本：" % len(allids) + " / ".join("%s %d" % (k, len(v)) for k, v in plan.items()))

# ---------- 1. 备份整个 db ----------
bakdb = os.path.join(BAK_DIR, "workbench_before_batch1.db")
if not os.path.exists(bakdb):
    t0 = time.time()
    shutil.copy2(DB, bakdb)
    print("db 备份完成 %.1f 秒 → %s (%.2f GB)" % (time.time() - t0, bakdb, os.path.getsize(bakdb) / 1e9))

# ---------- 2. 导出待删正文 ----------
export = {"清单": {}, "正文": {}}
for g, rows in plan.items():
    export["清单"][g] = [{"id": b, "title": t, "chars": n, "tier": ti, "score": sc} for b, t, n, ti, sc in rows]
for bid in allids:
    chs = c.execute("select page_from, content from book_chunks where book_id=? order by page_from, id", (bid,)).fetchall()
    export["正文"][bid] = [[p, x] for p, x in chs]
exp_path = os.path.join(BAK_DIR, "待删正文导出.json")
with open(exp_path, "w", encoding="utf-8") as f:
    json.dump(export, f, ensure_ascii=False)
print("正文导出 %.1f MB → %s" % (os.path.getsize(exp_path) / 1e6, exp_path))

# ---------- 3. 删库记录 ----------
tables_has_bookid = [r[0] for r in c.execute("select name from sqlite_master where type='table'")
                     if any(col[1] == "book_id" for col in c.execute("pragma table_info(%s)" % r[0]))]
print("含 book_id 的表：", tables_has_bookid)
ph = ",".join("?" * len(allids))
deleted = {}
for tb in tables_has_bookid:
    before = c.execute("select count(*) from %s" % tb).fetchone()[0]
    c.execute("delete from %s where book_id in (%s)" % (tb, ph), allids)
    after = c.execute("select count(*) from %s" % tb).fetchone()[0]
    if before != after:
        deleted[tb] = before - after
c.execute("delete from books where id in (%s)" % ph, allids)
c.commit()

# ---------- 4. 校验 ----------
left = c.execute("select count(*) from books").fetchone()[0]
chars = c.execute("select sum(length(content)) from book_chunks").fetchone()[0]
print("\n删除行数：", deleted)
print("剩余 books %d 本 / %d 字" % (left, chars))
c.close()
