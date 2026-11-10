# -*- coding: utf-8 -*-
"""给 books 表打分类（规则版，不烧 token）：先按顶层目录，再按书名关键词兜底。

写 books.category。未命中的标「待定」。
"""
import os
import re
import sqlite3
import sys

DB = r"E:\desktop\media\workbench.db"

# 顶层目录 → 分类（用户自己的系列名本身就带语义）
DIR_MAP = [
    ("权谋相关", "权谋与厚黑"),
    ("12-【帝王之术】", "权谋与厚黑"),
    ("29-【厚黑绝学】", "权谋与厚黑"),
    ("7-【人性天书】", "人性与操控"),
    ("_分类\\情感与关系", "情感与关系"),
    ("3-【王阳明】", "国学与心学"),
    ("5-【开窍之书】", "国学与心学"),
    ("38-【开窍开智开悟】", "国学与心学"),
    ("毛泽东", "毛选与政治"),
    ("1-75本经商", "商业与经营"),
    ("2-100本新媒体", "商业与营销"),
    ("26-【超级商业模式】", "商业与经营"),
    ("18-【股票投资】", "财富与投资"),
    ("10-【高敏感人格】", "心理与人格"),
    ("【CH118】心理学", "心理与人格"),
    ("2-【开悟】", "心理与认知"),
    ("22-【认知觉醒】", "心理与认知"),
    ("11-【思维训练】", "思维与方法"),
    ("31-【超级记忆】", "思维与方法"),
    ("9-【个人提升】", "个人成长"),
    ("6-【强者打造】", "个人成长"),
    ("8-【养精蓄锐】", "身心与养生"),
    ("27-【冥想系列】", "冥想与身心"),
    ("19-【职场提升】", "职场与体制"),
    ("16-【赢家系列】", "个人成长"),
    ("人性开悟14本", "人性与操控"),
    ("天涯", "杂谈与江湖"),
    ("root", "其他"),
]

TITLE_RULES = [
    ("权谋与厚黑", r"权谋|厚黑|帝王|权术|谋略|小人|官场|厚黑学|鬼谷|罗织|反经|止学|素书|商君|韩非|战国策|贞观"),
    ("国学与心学", r"王阳明|传习录|论语|道德经|庄子|孟子|荀子|易经|周易|黄帝内经|中庸|大学|心学|禅|佛"),
    ("毛选与政治", r"毛泽东|毛选|马克思|列宁|社会主义|共产党|政治|国家与革命|实践论|矛盾论|持久战|阶级|革命|新民主主义|为人民服务|反对"),
    ("商业与经营", r"商业|经商|创业|生意|经营|品牌|定位|管理|领导力|组织|稻盛|德鲁克|华为|战略|供应链"),
    ("商业与营销", r"营销|文案|广告|流量|带货|私域|电商|销售|爆款|选题|新媒体|种草|直播"),
    ("财富与投资", r"投资|理财|股票|股市|基金|经济|金融|财商|货币|资本|周期|巴菲特|索罗斯|估值|纳瓦尔|穷爸爸|小狗钱钱|财务自由|巴比伦|富有|财富|赚钱|钱"),
    ("心理与人格", r"心理|人格|情绪|依恋|敏感|创伤|抑郁|焦虑|成瘾|自恋|自卑|荣格|弗洛伊德|阿德勒"),
    ("心理与认知", r"认知|开悟|觉醒|正念|心流|意识|潜意识|脑科学|神经"),
    ("思维与方法", r"思维|思维导图|记忆|学习法|刻意练习|逻辑|批判性|金字塔|结构化|方法论"),
    ("个人成长", r"习惯|自律|效率|时间管理|精进|复盘|沟通|表达|口才|演讲|情商|成长|逆袭|强者"),
    ("身心与养生", r"养生|健康|睡眠|饮食|中医|运动|减肥|经络|瑜伽|按摩|排毒|食补"),
    ("冥想与身心", r"冥想|脉轮|能量|打坐|催眠|呼吸|灵性|吸引力|超感官"),
    ("历史与人物", r"历史|帝国|王朝|战争|文明|传记|自传|回忆录|曾国藩|朱元璋|曹操|张居正|梁启超"),
    ("文学与小说", r"小说|散文|诗集|故事|谈|读书|写作|许荣哲"),
    ("情感与关系", r"恋爱|感情|婚姻|两性|女人|男人|撩|搭讪|分手|亲密关系|PUA"),
    ("科学与技术", r"物理|数学|生物|量子|宇宙|进化|人工智能|算法|编程|计算机|数据"),
    ("职场与体制", r"职场|体制|公务员|处长|升迁|官场|面试|简历|摸鱼"),
    ("杂谈与江湖", r"天涯|帖子|江湖|杂谈|随笔|语录"),
]


def cat_by_path(p):
    p = (p or "").replace("/", "\\")
    for key, cat in DIR_MAP:
        if key in p:
            return cat
    return None


def cat_by_title(t):
    for cat, rx in TITLE_RULES:
        if re.search(rx, t or ""):
            return cat
    return None


def main():
    apply = "--apply" in sys.argv
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = c.execute("select id,title,source_path,category from books").fetchall()

    # 每本书取前两块的正文当证据
    sample = {}
    for r in c.execute("select book_id,content from book_chunks order by book_id,page_from"):
        sample.setdefault(r["book_id"], "")
        if len(sample[r["book_id"]]) < 1500:
            sample[r["book_id"]] += r["content"][:1500]

    def score(text):
        text = text or ""
        best, bestn = None, 0
        for cat, rx in TITLE_RULES:
            n = len(re.findall(rx, text))
            if n > bestn:
                best, bestn = cat, n
        return best if bestn >= 2 else None

    stat = {}
    todo = []
    for r in rows:
        cat = (cat_by_path(r["source_path"]) or cat_by_title(r["title"])
               or score((r["title"] or "") * 2 + sample.get(r["id"], "")))
        cat = cat or "待定"
        stat[cat] = stat.get(cat, 0) + 1
        todo.append((cat, r["id"], r["title"]))

    print("共 %d 本" % len(rows))
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        print("  %-10s %4d 本" % (k, v))

    und = [t for cat, i, t in todo if cat == "待定"]
    if und:
        print("\n待定 %d 本，前 25：" % len(und))
        for t in und[:25]:
            print("   ", t[:56])

    if not apply:
        print("\n（加 --apply 才写库）")
        return
    c.execute("update books set category='' where category is null")
    for cat, bid, t in todo:
        c.execute("update books set category=? where id=?", (cat, bid))
    c.commit()
    c.close()
    print("\n已写入 books.category")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
