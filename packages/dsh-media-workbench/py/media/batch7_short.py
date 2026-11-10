# -*- coding: utf-8 -*-
"""批7：删 242 本短书（<2万字）+ 中英双版的中文版"""
import json, os, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BAK = r"E:\desktop\书库盘点\_清理备份_20261107_批7"
os.makedirs(BAK, exist_ok=True)
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()

rows = q("""select b.id, b.title, coalesce(x.n,0)
            from books b left join (select book_id, sum(length(content)) n from book_chunks group by book_id) x
            on x.book_id=b.id""")
targets = []
for bid, t, n in rows:
    if n < 20000:
        targets.append((bid, t, n))
    elif "家庭私有制和国家的起源" in t and "英文版" not in t:
        targets.append((bid, t, n))     # 中英双版，删中文（用户要求留英文原版）

print("待删 %d 本（短书 %d + 中文版 1）" % (
    len(targets), sum(1 for _, _, n in targets if n < 20000)))
print("其中字数分布:", sorted(set(n for _, _, n in targets))[:8], "...")
for bid, t, n in sorted(targets, key=lambda x: -x[2])[:10]:
    print("   %s字｜%s" % (n, t[:50]))

exp = {}
for bid, t, n in targets:
    exp[bid] = {"title": t, "chunks": [[p, x] for p, x in q(
        "select page_from, content from book_chunks where book_id=?", (bid,))]}
json.dump(exp, open(os.path.join(BAK, "待删短书正文.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("正文备份 %.1f MB" % (os.path.getsize(os.path.join(BAK, "待删短书正文.json")) / 1e6))

ids = [b for b, _, _ in targets]
ph = ",".join("?" * len(ids))
tabs = [r[0] for r in q("select name from sqlite_master where type='table'")
        if any(col[1] == "book_id" for col in c.execute("pragma table_info(%s)" % r[0]))]
for tb in tabs:
    c.execute("delete from %s where book_id in (%s)" % (tb, ph), ids)
c.execute("delete from books where id in (%s)" % ph, ids)
c.commit()

print("\n现库 %d 本 / %d 块 / %d 字" % (
    q("select count(*) from books")[0][0], q("select count(*) from book_chunks")[0][0],
    q("select sum(length(content)) from book_chunks")[0][0]))
print("最短的书：%s" % q("""select b.title, x.n from books b join
        (select book_id, sum(length(content)) n from book_chunks group by book_id) x on x.book_id=b.id
        order by x.n limit 5"""))
c.close()
