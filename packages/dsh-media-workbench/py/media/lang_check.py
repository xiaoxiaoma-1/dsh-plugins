# -*- coding: utf-8 -*-
"""验证：'中文占比低'的书到底是英文原版还是乱码"""
import re, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()

SAMPLES = ["强到没有人能忽视你", "埃隆·马斯克传", "自己的MBA", "48-权力的48条法则",
           "被偷走的专注力", "017The Republic", "权力48条法则"]
o = []
for kw in SAMPLES:
    r = q("select id, title from books where title like ?", ("%" + kw + "%",))
    if not r:
        o.append("【%s】库里没找到" % kw)
        continue
    bid, t = r[0]
    ch = q("select content from book_chunks where book_id=? order by page_from limit 1", (bid,))
    txt = (ch[0][0] if ch else "")[:400].replace("\n", " ")
    en = len(re.findall(r"[A-Za-z]{3,}", txt))
    cn = sum(1 for x in txt if "\u4e00" <= x <= "\u9fff")
    bad = sum(1 for x in txt if 0xE000 <= ord(x) <= 0xF8FF or 0x80 <= ord(x) <= 0xFF)
    o.append("【%s】" % t[:40])
    o.append("   英文单词 %d 个 / 汉字 %d 个 / 可疑符号 %d 个" % (en, cn, bad))
    o.append("   开头: %s" % txt[:260])

o.append("")
o.append("=" * 40)
o.append("【全库分类：中文书 / 英文书 / 真乱码】")
rows = q("select id, title from books")
cn_books, en_books, garble = [], [], []
for bid, t in rows:
    chs = q("select content from book_chunks where book_id=? limit 8", (bid,))
    txt = "".join(x[0] or "" for x in chs)[:20000]
    if not txt:
        garble.append((t, 0, 0))
        continue
    cn = sum(1 for x in txt if "\u4e00" <= x <= "\u9fff")
    en = len(re.findall(r"[A-Za-z]{3,}", txt))
    priv = sum(1 for x in txt if 0xE000 <= ord(x) <= 0xF8FF or 0x80 <= ord(x) <= 0xFF)
    ratio_cn = cn / len(txt)
    ratio_priv = priv / len(txt)
    if ratio_cn > 0.15:
        cn_books.append(t)
    elif ratio_priv > 0.25 and en < len(txt) / 60:
        garble.append((t, round(ratio_cn, 2), round(ratio_priv, 2)))
    else:
        en_books.append(t)
o.append("中文书 %d 本 / 英文书 %d 本 / 真乱码 %d 本" % (len(cn_books), len(en_books), len(garble)))
o.append("")
o.append("【真乱码书】")
for t, rc, rp in garble:
    o.append("   %s（汉字%.2f 乱码字符%.2f）" % (t[:50], rc, rp))
open(r"E:\desktop\media\_lang_check.txt", "w", encoding="utf-8").write("\n".join(str(x) for x in o))
print("中文 %d / 英文 %d / 乱码 %d" % (len(cn_books), len(en_books), len(garble)))
