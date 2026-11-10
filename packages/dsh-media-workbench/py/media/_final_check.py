# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db", timeout=30)
q = lambda s: c.execute(s).fetchall()
print("books        ", q("select count(*) from books")[0][0])
print("book_chunks  ", q("select count(*) from book_chunks")[0][0])
print("chunks_fts   ", q("select count(*) from chunks_fts")[0][0])
print("总字数        ", q("select sum(length(content)) from book_chunks")[0][0])
print()
# 按书核对块数（比 not exists 快）
a = dict(q("select book_id, count(*) from book_chunks group by book_id"))
b = dict(q("select book_id, count(*) from chunks_fts group by book_id"))
diff = {k: (a.get(k, 0), b.get(k, 0)) for k in set(a) | set(b) if a.get(k, 0) != b.get(k, 0)}
print("块数不一致的书：%d 本" % len(diff))
for k, v in list(diff.items())[:8]:
    t = c.execute("select title from books where id=?", (k,)).fetchone()
    print("   %s chunks=%d fts=%d" % (t[0][:30] if t else k, v[0], v[1]))
print()
print("fts 幽灵行（书已删）", q("select count(*) from chunks_fts where book_id not in (select id from books)")[0][0])
print("孤儿块（书已删）    ", q("select count(*) from book_chunks where book_id not in (select id from books)")[0][0])
print("缺分类的书          ", q("select count(*) from books where id not in (select book_id from book_labels)")[0][0])
print()
print("== 检索验证 ==")
for kw in ["权 力", "王 阳 明", "毛 泽 东", "钩 子", "知 行 合 一", "隐 藏 的 潜 力"]:
    n = q("select count(*) from chunks_fts where tok match '\"%s\"'" % kw)[0][0]
    print("  %-16s -> %d 条" % (kw, n))
