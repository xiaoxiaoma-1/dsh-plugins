# -*- coding: utf-8 -*-
import re
import sqlite3

RULES = [
    ("国学与心学", r"王阳明|传习录|论语|道德经|庄子|孟子|荀子|易经|周易|黄帝内经|中庸|大学|心学|禅|佛"),
    ("冥想与身心", r"冥想|脉轮|能量|打坐|催眠|呼吸|灵性|吸引力|超感官"),
    ("财富与投资", r"投资|理财|股票|股市|基金|经济|金融|财商|货币|资本|周期|巴菲特|索罗斯|估值|纳瓦尔|穷爸爸|小狗钱钱|财务自由|巴比伦|富有|财富|赚钱|钱"),
    ("科学与技术", r"物理|数学|生物|量子|宇宙|进化|人工智能|算法|编程|计算机|数据"),
]

c = sqlite3.connect(r"E:\desktop\media\workbench.db")
row = c.execute("select id,title,category from books where title like '%六边形%' limit 1").fetchone()
print("书名:", row[1], "| 分类:", row[2])
txt = c.execute("select group_concat(content,'') from (select content from book_chunks where book_id=? limit 2)", (row[0],)).fetchone()[0] or ""
print("正文样本长度:", len(txt))
print("\n命中情况：")
for cat, rx in RULES:
    hits = re.findall(rx, txt)
    if hits:
        print("  %-8s 命中 %d 次：%s" % (cat, len(hits), "、".join(sorted(set(hits))[:6])))
c.close()
