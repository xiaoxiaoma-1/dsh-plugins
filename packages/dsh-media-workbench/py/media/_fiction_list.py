# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()
print("=== 判为小说的 21 本 ===")
for bid, t, ty, why in q("""select b.id, b.title, f.type, f.why from book_fiction f join books b on b.id=f.book_id
                            where f.fiction=1 order by b.title"""):
    n = q("select sum(length(content)) from book_chunks where book_id=?", (bid,))[0][0]
    print("   %s字｜%s｜%s" % (n, t[:48], why))
print()
print("=== 判为其他非虚构（可能混进小说）===")
for bid, t, why in q("""select b.id, b.title, f.why from book_fiction f join books b on b.id=f.book_id
                        where f.type='其他非虚构' order by b.title"""):
    n = q("select sum(length(content)) from book_chunks where book_id=?", (bid,))[0][0]
    print("   %s字｜%s｜%s" % (n, t[:48], why))
