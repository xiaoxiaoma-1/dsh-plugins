# -*- coding: utf-8 -*-
import sqlite3, sys
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()
print("books %d / chunks %d / fts %d / 字数 %d" % (
    q("select count(*) from books")[0][0], q("select count(*) from book_chunks")[0][0],
    q("select count(*) from chunks_fts")[0][0], q("select sum(length(content)) from book_chunks")[0][0]))
print()
print("保留书的档位分布:", Counter(r[0] for r in q("select tier from book_quality")).most_common())
print("抽坏（intact=0）仍留在库:", q("select count(*) from book_quality where intact=0")[0][0], "本")
print()
print("== 抽坏的里面字数最多的 12 本 ==")
for r in q("""select b.title, m.chars, m.pages, m.chars_per_page from book_quality qq
              join books b on b.id=qq.book_id join book_metric m on m.book_id=qq.book_id
              where qq.intact=0 order by m.chars desc limit 12"""):
    print("   %s字 %s页 %.1f字/页｜%s" % (r[1], r[2], r[3], r[0][:44]))
print()
print("== 英文书（中文占比 <30%）==")
rows = q("""select b.id, b.title, sum(length(cc.content)) n from books b join book_chunks cc on cc.book_id=b.id
            group by b.id""")
eng = []
for bid, t, n in rows:
    txt = q("select group_concat(substr(content,1,400),'') from (select content from book_chunks where book_id=? limit 20)", (bid,))[0][0] or ""
    if not txt:
        continue
    cn = sum(1 for ch in txt if "\u4e00" <= ch <= "\u9fff") / max(1, len(txt))
    if cn < 0.30:
        eng.append((t, n, round(cn, 2)))
print("共 %d 本" % len(eng))
for t, n, cn in sorted(eng, key=lambda x: -x[1]):
    print("   %s字 中文占比%.2f｜%s" % (n, cn, t[:50]))
