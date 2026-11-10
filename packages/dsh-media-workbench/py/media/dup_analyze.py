# -*- coding: utf-8 -*-
"""① 毛选详情 ② 全库重复书分析"""
import json, re, sqlite3, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()
o = []

# ========== ① 毛选 ==========
o.append("========== ① 毛选详情 ==========")
rows = q("""select b.id, b.title, coalesce(b.pages,0), sum(length(cc.content)) n, count(cc.id) cnt
            from books b join book_chunks cc on cc.book_id=b.id
            where b.title like '%毛泽东选集%' or b.title like '%毛选%'
            group by b.id order by b.title""")
for bid, t, p, n, cnt in rows:
    o.append("%-52s｜%s页 %s块 %s字" % (t[:52], p, cnt, n))
o.append("")
o.append("【每卷分册合计】")
vol = defaultdict(lambda: [0, 0, ""])
for bid, t, p, n, cnt in rows:
    m = re.search(r"第([一二三四12 34])卷", t)
    if m and "解读" not in t:
        k = m.group(1)
        vol[k][0] += n
        vol[k][1] += 1
        vol[k][2] = t
for k in sorted(vol):
    o.append("  第%s卷：%d 个文件，合计 %s 字" % (k, vol[k][1], vol[k][0]))
o.append("")
o.append("【完整本 041毛泽东选集.[第一卷] 的构成】")
r = q("select id, pages from books where title like '%041毛泽东选集%'")
if r:
    bid, pages = r[0]
    o.append("  页数 %s，块数 %s" % (pages, q("select count(*) from book_chunks where book_id=?", (bid,))[0][0]))
    for pf, txt in q("select page_from, substr(content,1,120) from book_chunks where book_id=? order by page_from limit 4", (bid,)):
        o.append("   页%s: %s" % (pf, (txt or "").replace("\n", " ")))
o.append("")
o.append("【分册样例：第1卷第1分册前 2 块】")
r = q("select id from books where title like '%毛泽东选集-第1卷-第1分册%'")
if r:
    for pf, txt in q("select page_from, substr(content,1,120) from book_chunks where book_id=? order by page_from limit 2", (r[0][0],)):
        o.append("   页%s: %s" % (pf, (txt or "").replace("\n", " ")))
o.append("")
o.append("【毛选解读 4 本】")
for bid, t, p, n, cnt in rows:
    if "解读" in t:
        o.append("  %s｜%s字 %s块 %s页" % (t[:40], n, cnt, p))

# ========== ② 去重 ==========
o.append("")
o.append("========== ② 全库重复书分析 ==========")
books = q("""select b.id, b.title, coalesce(b.author,''), coalesce(b.pages,0),
                    coalesce(x.n,0), coalesce(x.cnt,0)
             from books b left join
             (select book_id, sum(length(content)) n, count(*) cnt from book_chunks group by book_id) x
             on x.book_id=b.id""")
o.append("全库 %d 本" % len(books))

def norm_title(t):
    t = t or ""
    t = re.sub(r"[\[\(（【].{0,12}?(精品|完整版|全新|修订|增补|扫描版|高清|pdf|PDF|电子书|txt|插图版|珍藏).{0,8}?[\]\)）】]", "", t)
    t = re.sub(r"(全\d+册|全三册|全集|全本|完本|修订版|全新修订版|第[一二三四五六七八九十\d]+版|珍藏本|超值白金版|插图版|注音版|扫描版|高清完整版|pdf|PDF|txt)", "", t)
    t = re.sub(r"[《》「」\[\]【】\(\)（）:：，,。．\.、\-_—\s]+", "", t)
    return t.strip()

groups = defaultdict(list)
for bid, t, a, p, n, cnt in books:
    key = norm_title(t)
    if len(key) >= 3:
        groups[key].append((bid, t, a, p, n, cnt))

dups = {k: v for k, v in groups.items() if len(v) > 1}
o.append("归一化标题后重复的组：%d 组，涉及 %d 本" % (len(dups), sum(len(v) for v in dups.values())))
o.append("")
drop = []
for k, v in sorted(dups.items(), key=lambda x: -sum(y[4] for y in x[1])):
    v2 = sorted(v, key=lambda x: -x[4])
    o.append("【%s】%d 本 → 保留字数最多的" % (k[:30], len(v2)))
    for i, (bid, t, a, p, n, cnt) in enumerate(v2):
        mark = "★保留" if i == 0 else "  可删"
        o.append("   %s %s字 %s块 %s页｜%s｜%s" % (mark, n, cnt, p, t[:44], a[:14]))
        if i > 0:
            drop.append((bid, t, n))
o.append("")
o.append("按标题可直接删的重复本：%d 本，合计 %d 字" % (len(drop), sum(x[2] for x in drop)))

json.dump([{"id": b, "title": t, "chars": n} for b, t, n in drop],
          open(r"E:\desktop\media\_dup_candidates.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(r"E:\desktop\media\_wym_dup.txt", "w", encoding="utf-8").write("\n".join(str(x) for x in o))
print("毛选 %d 本；重复组 %d，可删 %d 本 %d 字" % (len(rows), len(dups), len(drop), sum(x[2] for x in drop)))
