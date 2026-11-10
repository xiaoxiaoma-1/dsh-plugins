"""删除书库审计判定为"垃圾"的书（267 本）

备份：元数据 + 每本前 200 字 → _deleted_garbage_books_<stamp>.json
然后删 book_chunks / book_topics / book_labels / books。
"""
import json
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
AUDIT = r"E:\desktop\media\_book_audit_sample.json"
STAMP = time.strftime("%Y%m%d_%H%M%S")
BAK = rf"E:\desktop\media\_deleted_garbage_books_{STAMP}.json"

rows = json.load(open(AUDIT, encoding="utf-8"))
bad = [x for x in rows if x["useful"] == "垃圾"]
ids = [x["id"] for x in bad]
print(f"待删 {len(ids)} 本")

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cur = c.cursor()

bak = []
for x in bad:
    b = cur.execute("select id,title,author,pages,source_path from books where id=?", (x["id"],)).fetchone()
    if not b:
        continue
    ch = cur.execute("select sum(chars), count(*) from book_chunks where book_id=?", (x["id"],)).fetchone()
    head = cur.execute("select content from book_chunks where book_id=? order by id limit 1", (x["id"],)).fetchone()
    bak.append({
        "id": b["id"], "title": b["title"], "author": b["author"], "pages": b["pages"],
        "source_path": b["source_path"], "chars": ch[0] or 0, "chunks": ch[1] or 0,
        "title_new": x.get("title_new"), "kind": x.get("kind"), "why": x.get("why"),
        "head200": ((head["content"] if head else "") or "")[:200],
    })
with open(BAK, "w", encoding="utf-8") as f:
    json.dump(bak, f, ensure_ascii=False, indent=1)
print("已备份元数据 ->", BAK)

q = ",".join("?" * len(ids))
stats = {}
for t, key in [("book_chunks", "book_id"), ("book_topics", "book_id"),
               ("book_labels", "book_id"), ("split_items", "book_id")]:
    try:
        n = cur.execute(f"delete from {t} where {key} in ({q})", ids).rowcount
        stats[t] = n
    except Exception as e:
        stats[t] = f"跳过({e})"
n = cur.execute(f"delete from books where id in ({q})", ids).rowcount
stats["books"] = n
c.commit()

left = cur.execute("select count(*) from books").fetchone()[0]
print("删除明细:", stats)
print("书库剩余:", left, "本")
c.close()
