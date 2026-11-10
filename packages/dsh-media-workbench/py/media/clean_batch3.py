# -*- coding: utf-8 -*-
"""批3：删真重复 7 本（剔除英文版/中文版误判）"""
import json, os, re, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BAK = r"E:\desktop\书库盘点\_清理备份_20261107_批3"
os.makedirs(BAK, exist_ok=True)
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()

drop = json.load(open(r"E:\desktop\media\_dup_drop.json", encoding="utf-8"))

def cn_ratio(bid):
    txt = "".join(x[0] or "" for x in q("select content from book_chunks where book_id=?", (bid,)))
    if not txt:
        return 0
    cn = sum(1 for ch in txt[:200000] if "\u4e00" <= ch <= "\u9fff")
    return cn / min(len(txt), 200000)

final = []
for x in drop:
    r = cn_ratio(x["id"])
    x["cn"] = round(r, 2)
    # 语言不同不算重复：剔除英文版（中文占比 < 30%）
    if r < 0.30:
        print("跳过（英文/非中文书，语言不同不算重复）：%s  中文占比 %.2f" % (x["title"][:40], r))
        continue
    final.append(x)

print("最终删除 %d 本：" % len(final))
for x in final:
    print("   %s字 中文占比%.2f｜%s" % (x["chars"], x["cn"], x["title"][:46]))

ids = [x["id"] for x in final]
export = {"清单": final, "正文": {}}
for bid in ids:
    export["正文"][bid] = [[p, t] for p, t in q(
        "select page_from, content from book_chunks where book_id=? order by page_from, id", (bid,))]
p = os.path.join(BAK, "待删正文导出.json")
json.dump(export, open(p, "w", encoding="utf-8"), ensure_ascii=False)
print("正文备份 %.1f MB" % (os.path.getsize(p) / 1e6))

ph = ",".join("?" * len(ids))
tabs = [r[0] for r in q("select name from sqlite_master where type='table'")
        if any(col[1] == "book_id" for col in c.execute("pragma table_info(%s)" % r[0]))]
for tb in tabs:
    c.execute("delete from %s where book_id in (%s)" % (tb, ph), ids)
c.execute("delete from books where id in (%s)" % ph, ids)
c.commit()
print("剩余 %d 本 / %d 块 / %d 字" % (
    q("select count(*) from books")[0][0], q("select count(*) from book_chunks")[0][0],
    q("select sum(length(content)) from book_chunks")[0][0]))
c.close()
