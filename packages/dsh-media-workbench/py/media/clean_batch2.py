# -*- coding: utf-8 -*-
"""批2：删「泛泛但正常」39 本（用户：做减法，全删）"""
import json, os, re, shutil, sqlite3, sys, time
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BAK = r"E:\desktop\书库盘点\_清理备份_20261107_批2"
os.makedirs(BAK, exist_ok=True)

c = sqlite3.connect(DB)
d = json.load(open(r"E:\desktop\media\_quality_tier.json", encoding="utf-8"))

def info(bid):
    r = c.execute("select title from books where id=?", (bid,)).fetchone()
    n = c.execute("select coalesce(sum(length(content)),0) from book_chunks where book_id=?", (bid,)).fetchone()[0]
    return (r[0] if r else "?"), n

NOVEL = re.compile(r"(小说|叙事|情节|文学|散文|诗歌|诗集|玄幻|言情|穿越|晋江|琅琊榜|上册|下册|共\d册|三部曲|传奇)")
GARBAGE = re.compile(r"(乱码|符号|无有效|拼凑|跳跃|重复|图片|碎片|不连续|扫描|广告|招商)")

target = []
for bid, v in d.items():
    if v.get("tier") != "C":
        continue
    t, n = info(bid)
    if not t or t == "?":
        continue
    why = v.get("why") or ""
    if "付费文章" in t or "老A" in t:
        continue
    if NOVEL.search(t + why) or GARBAGE.search(why):
        continue
    target.append((bid, t, n, v.get("score")))

print("待删「泛泛但正常」%d 本，合计 %d 字" % (len(target), sum(x[2] for x in target)))
for bid, t, n, sc in sorted(target, key=lambda x: -x[2])[:12]:
    print("   %s字 %s分｜%s" % (n, sc, t[:44]))

ids = [x[0] for x in target]
# 导出正文备份
export = {"清单": [{"id": b, "title": t, "chars": n, "score": sc} for b, t, n, sc in target], "正文": {}}
for bid in ids:
    export["正文"][bid] = [[p, x] for p, x in c.execute(
        "select page_from, content from book_chunks where book_id=? order by page_from, id", (bid,))]
p = os.path.join(BAK, "待删正文导出.json")
json.dump(export, open(p, "w", encoding="utf-8"), ensure_ascii=False)
print("正文导出 %.1f MB → %s" % (os.path.getsize(p) / 1e6, p))

ph = ",".join("?" * len(ids))
tabs = [r[0] for r in c.execute("select name from sqlite_master where type='table'")
        if any(col[1] == "book_id" for col in c.execute("pragma table_info(%s)" % r[0]))]
print("会触及的表：", tabs)
dele = {}
for tb in tabs:
    b0 = c.execute("select count(*) from %s" % tb).fetchone()[0]
    c.execute("delete from %s where book_id in (%s)" % (tb, ph), ids)
    b1 = c.execute("select count(*) from %s" % tb).fetchone()[0]
    if b0 != b1:
        dele[tb] = b0 - b1
c.execute("delete from books where id in (%s)" % ph, ids)
c.commit()
print("删除行数：", dele)
print("剩余 %d 本 / %d 块 / %d 字" % (
    c.execute("select count(*) from books").fetchone()[0],
    c.execute("select count(*) from book_chunks").fetchone()[0],
    c.execute("select sum(length(content)) from book_chunks").fetchone()[0]))
c.close()
