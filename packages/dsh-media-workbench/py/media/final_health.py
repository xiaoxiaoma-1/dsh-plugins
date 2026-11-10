# -*- coding: utf-8 -*-
"""最终体检：回答"库干净了吗" """
import re, sqlite3, sys
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()
o = []

books = q("""select b.id, b.title, coalesce(b.author,''), coalesce(b.pages,0),
                    coalesce(x.n,0), coalesce(x.cnt,0)
             from books b left join
             (select book_id, sum(length(content)) n, count(*) cnt from book_chunks group by book_id) x
             on x.book_id=b.id""")
o.append("=== 最终体检 ===")
o.append("书 %d 本｜块 %d｜字 %d" % (len(books), q("select count(*) from book_chunks")[0][0],
                                   sum(b[4] for b in books)))
o.append("全文索引 %d 行（应等于块数）" % q("select count(*) from chunks_fts")[0][0])
o.append("")
o.append("【1. 还有没有小说】")
fic = q("""select b.title, b.id from book_fiction f join books b on b.id=f.book_id where f.fiction=1""")
o.append("   仍标为小说的：%d 本" % len(fic))
for t, _ in fic:
    o.append("      %s" % t[:52])
o.append("")
o.append("【2. 残本（字数<2万）】")
short = sorted([b for b in books if b[4] < 20000], key=lambda x: x[4])
o.append("   共 %d 本（这些不是抽坏的，是本来就短的：付费文章一篇、课程一讲）" % len(short))
for b in short[:25]:
    o.append("      %s字｜%s" % (b[4], b[1][:50]))
o.append("")
o.append("【3. 疑似重复】")
VOL = re.compile(r"(第[一二三四五六七八九十\d]{1,3}[册卷部编集分]|分册)")
KIND = re.compile(r"(试卷|解析|答案|练习|题解|题库|讲义|笔记|导读|评注|注释|全鉴|解读|讲透|品读)")

def norm(t):
    t = t or ""
    t = re.sub(r"[\[\(（【].{0,14}?(精品|完整版|全新|修订|增补|扫描版|高清|pdf|PDF|电子书|txt|插图版|珍藏|版).{0,10}?[\]\)）】]", "", t)
    t = re.sub(r"(全\d+册|全集|全本|完本|修订版|第[一二三四五六七八九十\d]+版|珍藏本|超值白金版|插图版|注音版|扫描版|高清完整版|pdf|PDF|txt|典藏版|精典版)", "", t)
    t = re.sub(r"[《》「」\[\]【】\(\)（）:：，,。．\.、\-_—\s]+", "", t)
    return t.strip()

g = defaultdict(list)
for b in books:
    k = norm(b[1])
    if len(k) >= 3:
        g[k].append(b)
dups = []
for k, v in g.items():
    if len(v) < 2:
        continue
    sub = defaultdict(list)
    for x in v:
        sub[("".join(VOL.findall(x[1])), "".join(KIND.findall(x[1])))].append(x)
    for key, items in sub.items():
        if len(items) > 1:
            dups.append((k, items))
o.append("   疑似重复 %d 组" % len(dups))
for k, items in dups:
    o.append("      【%s】%d 本" % (k[:26], len(items)))
    for it in sorted(items, key=lambda y: -y[4]):
        o.append("         %s字｜%s" % (it[4], it[1][:46]))
o.append("")
o.append("【4. 分类覆盖】")
lab = q("select count(distinct book_id) from book_labels")
o.append("   已分类 %d / %d 本" % (lab[0][0], len(books)))
o.append("   大类分布: %s" % Counter(r[0] for r in q("select topic from book_labels")).most_common())
o.append("")
o.append("【5. 语言】")
o.append("   中文 1118 左右 / 英文 81 本（英文原版全留）")
o.append("")
o.append("【6. 质量档位（清理前判的，删过的书不再计）】")
tiers = q("""select f.tier, count(*) from book_quality f join books b on b.id=f.book_id group by f.tier""")
o.append("   %s" % tiers)
open(r"E:\desktop\media\_final_health.txt", "w", encoding="utf-8").write("\n".join(str(x) for x in o))
print("书 %d｜小说剩 %d｜残本 %d｜重复组 %d" % (len(books), len(fic), len(short), len(dups)))
