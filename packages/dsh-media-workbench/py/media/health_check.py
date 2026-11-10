# -*- coding: utf-8 -*-
"""① 删掉已补新版的 8 本旧版 ② 全库体检"""
import json, os, re, sqlite3, sys
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BAK = r"E:\desktop\书库盘点\_清理备份_20261107_批5"
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()

# ===== ① 删旧版（保留数字化定量分析，因为它新版没入库成功）=====
NEW_TITLES = ["走进我的交易室", "游戏改变世界", "短线交易大师", "异类", "穿布鞋的马云",
              "炒股的智慧", "设计中的设计", "传统企业如何做电商"]
rows = q("""select qq.book_id, b.title from book_quality qq join books b on b.id=qq.book_id
            where qq.intact=0""")
oldids = []
for bid, t in rows:
    if "数字化定量分析" in (t or ""):
        continue
    if any(nt in (t or "") for nt in NEW_TITLES):
        oldids.append((bid, t))
if oldids:
    exp = {b: {"title": t, "chunks": [[p, x] for p, x in q(
        "select page_from, content from book_chunks where book_id=?", (b,))]} for b, t in oldids}
    json.dump(exp, open(os.path.join(BAK, "旧版待删正文.json"), "w", encoding="utf-8"), ensure_ascii=False)
    ids = [b for b, _ in oldids]
    ph = ",".join("?" * len(ids))
    tabs = [r[0] for r in q("select name from sqlite_master where type='table'")
            if any(col[1] == "book_id" for col in c.execute("pragma table_info(%s)" % r[0]))]
    for tb in tabs:
        c.execute("delete from %s where book_id in (%s)" % (tb, ph), ids)
    c.execute("delete from books where id in (%s)" % ph, ids)
    c.commit()
    print("删掉已被新版替换的旧版 %d 本：%s" % (len(ids), [t[:20] for _, t in oldids]))

# ===== ② 体检 =====
o = []
books = q("""select b.id, b.title, coalesce(b.author,''), coalesce(b.pages,0),
                    coalesce(x.n,0), coalesce(x.cnt,0)
             from books b left join
             (select book_id, sum(length(content)) n, count(*) cnt from book_chunks group by book_id) x
             on x.book_id=b.id""")
o.append("=== 全库体检（%d 本）===" % len(books))
o.append("总字数 %d" % sum(b[4] for b in books))
o.append("")
o.append("【字数分布】")
bins = [(0, 5000), (5000, 20000), (20000, 100000), (100000, 300000), (300000, 10 ** 9)]
for lo, hi in bins:
    n = sum(1 for b in books if lo <= b[4] < hi)
    o.append("   %s~%s 字：%d 本" % (lo, "∞" if hi > 10 ** 8 else hi, n))
o.append("")
o.append("【字数最少的 20 本（残本嫌疑）】")
for b in sorted(books, key=lambda x: x[4])[:20]:
    cpp = b[4] / b[3] if b[3] else 0
    o.append("   %s字 %s页 %.0f字/页｜%s" % (b[4], b[3], cpp, b[1][:48]))
o.append("")
o.append("【每页字数最少的 15 本（抽坏嫌疑，排除无页数）】")
for b in sorted([x for x in books if x[3] > 5], key=lambda x: x[4] / x[3])[:15]:
    o.append("   %s字 %s页 %.1f字/页｜%s" % (b[4], b[3], b[4] / b[3], b[1][:48]))
o.append("")

# 乱码检测
def cn_ratio(bid):
    t = "".join(x[0] or "" for x in q("select content from book_chunks where book_id=? limit 5", (bid,)))
    if not t:
        return 0
    return sum(1 for ch in t[:50000] if "\u4e00" <= ch <= "\u9fff") / min(len(t), 50000)

o.append("【乱码嫌疑（中文字符占比 <15% 且非英文书）】")
bad = []
for b in books:
    r = cn_ratio(b[0])
    if r < 0.15:
        bad.append((b[1], b[4], round(r, 2)))
o.append("   共 %d 本" % len(bad))
for t, n, r in sorted(bad, key=lambda x: -x[1])[:25]:
    o.append("   %s字 中文占比%.2f｜%s" % (n, r, t[:50]))

# 重复检测 v2
VOL = re.compile(r"(第[一二三四五六七八九十\d]{1,3}[册卷部编集分]|分册|上[册中下]?|下[册中下]?|[上中下]篇)")
KIND = re.compile(r"(试卷|解析|答案|练习|题解|题库|讲义|笔记|导读|评注|注释|全鉴|解读|讲透|品读)")

def norm(t):
    t = t or ""
    t = re.sub(r"[\[\(（【].{0,14}?(精品|完整版|全新|修订|增补|扫描版|高清|pdf|PDF|电子书|txt|插图版|珍藏|版).{0,10}?[\]\)）】]", "", t)
    t = re.sub(r"(全\d+册|全集|全本|完本|修订版|全新修订版|第[一二三四五六七八九十\d]+版|珍藏本|超值白金版|插图版|注音版|扫描版|高清完整版|pdf|PDF|txt|典藏版|精典版)", "", t)
    t = re.sub(r"[《》「」\[\]【】\(\)（）:：，,。．\.、\-_—\s]+", "", t)
    return t.strip()

groups = defaultdict(list)
for b in books:
    k = norm(b[1])
    if len(k) >= 3:
        groups[k].append(b)
dups = []
for k, v in groups.items():
    if len(v) < 2:
        continue
    sub = defaultdict(list)
    for x in v:
        sub[("".join(VOL.findall(x[1])), "".join(KIND.findall(x[1])))].append(x)
    for key, items in sub.items():
        if len(items) > 1:
            dups.append((k, key, sorted(items, key=lambda y: -y[4])))
o.append("")
o.append("【疑似重复（%d 组）】" % len(dups))
for k, key, items in dups:
    o.append("   【%s】%d 本" % (k[:24], len(items)))
    for i, it in enumerate(items):
        o.append("      %s %s字｜%s" % ("★" if i == 0 else "  ", it[4], it[1][:44]))

open(r"E:\desktop\media\_health_check.txt", "w", encoding="utf-8").write("\n".join(str(x) for x in o))
print("体检完成：%d 本，字数<2万 %d 本，乱码嫌疑 %d 本，疑似重复 %d 组" % (
    len(books), sum(1 for b in books if b[4] < 20000), len(bad), len(dups)))
c.close()
