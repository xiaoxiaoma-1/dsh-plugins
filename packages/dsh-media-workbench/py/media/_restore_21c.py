# -*- coding: utf-8 -*-
"""恢复被误删的《21世纪资本论》（皮凯蒂，不是马克思资本论）"""
import json, os, sqlite3, sys, time
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BAK = r"E:\desktop\书盘盘点\_清理备份_20261107_批6"
BAK = r"E:\desktop\书库盘点\_清理备份_20261107_批6"
data = json.load(open(os.path.join(BAK, "待删正文.json"), encoding="utf-8"))

target = None
for bid, v in data.items():
    if "21世纪资本论" in v["title"]:
        target = (bid, v)
        break
if not target:
    print("没找到"); sys.exit(1)
bid, v = target
print("恢复：", v["title"], "共", len(v["chunks"]), "块")

c = sqlite3.connect(DB)
now = time.strftime("%Y-%m-%d %H:%M:%S")
total = sum(len(x[1] or "") for x in v["chunks"])
c.execute("delete from books where id=?", (bid,))
c.execute("insert into books(id,title,author,source_path,pages,ocr_state,quality,summary,doable,category,created_at)"
          " values(?,?,?,?,?,?,?,?,?,?,?)",
          (bid, v["title"], "托马斯·皮凯蒂", "", max(1, total // 1000), "done", "", "", "", "", now))
for i, (pf, content) in enumerate(v["chunks"]):
    c.execute("insert or replace into book_chunks(id,book_id,page_from,page_to,heading,content,chars,created_at)"
              " values(?,?,?,?,?,?,?,?)",
              ("%s_c%04d" % (bid, i), bid, pf, pf, "", content, len(content or ""), now))
    c.execute("insert into chunks_fts(tok, content, book_id, page_from) values(?,?,?,?)",
              (" ".join(content or ""), content, bid, pf))
c.execute("insert or replace into book_labels values(?,?,?,?,?,?,?)",
          (bid, "商业与变现", "", "投资理财", "投资理财", 1.0, now))
c.commit()
print("已恢复 %d 块" % len(v["chunks"]))
print("现库 %d 本 / %d 块 / %d 字" % (
    c.execute("select count(*) from books").fetchone()[0],
    c.execute("select count(*) from book_chunks").fetchone()[0],
    c.execute("select sum(length(content)) from book_chunks").fetchone()[0]))
c.close()
