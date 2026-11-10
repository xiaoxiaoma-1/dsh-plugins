# -*- coding: utf-8 -*-
"""查最后 2 本未分类 + 最终完整性核对 + 清点备份目录"""
import os, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()

print("=== 未分类的书 ===")
for bid, t in q("select id, title from books where id not in (select book_id from book_classify)"):
    n = q("select sum(length(content)) from book_chunks where book_id=?", (bid,))[0][0]
    print("   %s字｜%s" % (n, t[:60]))
    ch = q("select content from book_chunks where book_id=? order by page_from limit 1", (bid,))
    print("   开头: %s" % ((ch[0][0] if ch else "")[:160].replace("\n", " ")))

print()
print("=== 完整性核对 ===")
checks = [
    ("书总数", "select count(*) from books"),
    ("正文块", "select count(*) from book_chunks"),
    ("全文索引", "select count(*) from chunks_fts"),
    ("总字数", "select sum(length(content)) from book_chunks"),
    ("已分类", "select count(*) from book_classify"),
    ("分类标签表", "select count(*) from book_labels"),
    ("孤儿块（书已删）", "select count(*) from book_chunks where book_id not in (select id from books)"),
    ("幽灵索引（书已删）", "select count(*) from chunks_fts where book_id not in (select id from books)"),
]
for name, sql in checks:
    print("   %-14s %s" % (name, q(sql)[0][0]))

# 按书核对块数一致性
a = dict(q("select book_id, count(*) from book_chunks group by book_id"))
b = dict(q("select book_id, count(*) from chunks_fts group by book_id"))
diff = {k: (a.get(k, 0), b.get(k, 0)) for k in set(a) | set(b) if a.get(k, 0) != b.get(k, 0)}
print("   块数与索引不一致的书 %d 本" % len(diff))

print()
print("=== 备份目录清点 ===")
for base in [r"E:\desktop\书库盘点", r"E:\desktop", "E:\\"]:
    if not os.path.isdir(base):
        continue
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d)
        if not os.path.isdir(p):
            continue
        if any(k in d for k in ("备份", "回收", "碎片", "副本", "清理备份")):
            size = 0
            cnt = 0
            for root, _, files in os.walk(p):
                for f in files:
                    try:
                        size += os.path.getsize(os.path.join(root, f))
                        cnt += 1
                    except Exception:
                        pass
            print("   %-58s %7.1f GB  %d 文件" % (p, size / 1e9, cnt))
c.close()
