# -*- coding: utf-8 -*-
"""书目分析：查重（同名/同大小/同哈希）+ 按方向分类 + 疑似无价值。只读。"""
import csv
import os
import re
import sys
import hashlib
from collections import defaultdict

OUT = r"E:\desktop\书库盘点"
ROOT = r"E:\wengao"

CATS = [
    ("商业·营销", ["商业", "经商", "创业", "生意", "营销", "品牌", "销售", "带货", "谈判", "定位", "流量", "私域", "电商", "广告", "文案"]),
    ("财富·投资", ["投资", "理财", "股票", "股市", "基金", "经济", "金融", "财商", "货币", "资本", "周期"]),
    ("管理·组织", ["管理", "领导力", "组织", "团队", "华为", "稻盛", "德鲁克", "执行"]),
    ("心理学", ["心理", "人格", "情绪", "认知", "潜意识", "依恋", "敏感", "创伤", "抑郁", "焦虑", "社会性"]),
    ("哲学·思想", ["哲学", "尼采", "康德", "黑格尔", "叔本华", "加缪", "萨特", "存在", "形而上", "逻辑", "思辨", "理性"]),
    ("国学·谋略", ["王阳明", "传习录", "论语", "道德经", "庄子", "孟子", "荀子", "孙子", "兵法", "史记", "资治通鉴", "易经", "周易", "黄帝内经", "权谋", "帝王", "厚黑", "曾国藩", "素书", "鬼谷子", "罗织", "商君", "韩非", "战国策", "贞观", "反经", "止学"]),
    ("人物·传记", ["传记", "自传", "传", "回忆录", "曾国藩", "毛泽东", "邓小平", "朱元璋", "曹操", "王石", "任正非", "乔布斯", "马斯克"]),
    ("成长·方法", ["习惯", "自律", "效率", "时间管理", "精进", "复盘", "沟通", "表达", "口才", "演讲", "思维", "学习", "记忆", "专注", "拖延", "情商"]),
    ("历史·文明", ["历史", "帝国", "王朝", "战争", "文明", "三国", "明朝", "清朝", "唐朝", "宋朝", "民国"]),
    ("社科·人文", ["社会", "人类", "文化", "政治", "制度", "阶层", "性别", "教育", "家庭", "婚姻"]),
    ("科学·技术", ["物理", "数学", "生物", "脑", "神经", "量子", "宇宙", "人工智能", "AI", "算法", "编程", "数据", "计算机"]),
    ("文学·小说", ["小说", "散文", "诗集", "遥远", "救世主", "三体", "斗罗", "斗破", "凡人修仙", "遮天", "完美世界", "剑来", "雪中", "诡秘", "重生", "穿越", "总裁", "玄幻", "修仙", "仙侠", "言情", "悬疑", "灵异", "都市", "兵王", "赘婿", "医仙", "龙王", "神级"]),
    ("教材·应试", ["考研", "四六级", "教材", "习题", "真题", "教程", "讲义", "试卷", "高考"]),
    ("健康·身心", ["养生", "健康", "睡眠", "饮食", "中医", "运动", "减肥", "经络", "瑜伽"]),
]

JUNK_HINT = ["合集", "大全", "打包", "整理版", "电子书", "资源", "下载", "网盘"]


def norm(s):
    s = s.lower()
    s = re.sub(r"\.(pdf|epub|mobi|ebk3|azw3|djvu|chm|txt|docx?|mht|mhtml)$", "", s)
    s = re.sub(r"[（(\[【][^）)\]】]{0,20}[）)\]】]", "", s)   # 去括号注释
    s = re.sub(r"(全译本|完整版|修订版|精校版|高清版|扫描版|电子版|文字版|典藏版|珍藏版|azw3|pdf|epub)", "", s)
    s = re.sub(r"[\s\.\-_·,，、:：;；'\"“”‘’]+", "", s)
    return s


def classify(name):
    hits = []
    for cat, kws in CATS:
        for k in kws:
            if k.lower() in name.lower():
                hits.append(cat)
                break
    return hits or ["未分类"]


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    rows = []
    with open(os.path.join(OUT, "书目清单.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["size"] = float(r["大小MB"])
            r["path"] = os.path.join(ROOT, r["相对路径"])
            r["norm"] = norm(r["文件名"])
            r["cats"] = classify(r["文件名"])
            rows.append(r)

    # --- 分类统计 ---
    cat_count = defaultdict(lambda: [0, 0.0])
    for r in rows:
        for c in r["cats"]:
            cat_count[c][0] += 1
            cat_count[c][1] += r["size"]
    print("== 按方向（一个文件可能命中多类）==")
    for c, (n, mb) in sorted(cat_count.items(), key=lambda kv: -kv[1][0]):
        print("%-10s %4d 个  %7.1f MB" % (c, n, mb))

    # --- 未分类样本 ---
    unc = [r for r in rows if r["cats"] == ["未分类"]]
    print("\n== 未分类 %d 个（前 25）==" % len(unc))
    for r in unc[:25]:
        print("   ", r["文件名"][:60])

    # --- 查重 ---
    by_norm = defaultdict(list)
    by_size = defaultdict(list)
    for r in rows:
        by_norm[r["norm"]].append(r)
        if r["size"] > 0.5:
            by_size[round(r["size"], 2)].append(r)

    groups = []
    for k, v in by_norm.items():
        if len(v) > 1:
            groups.append(("同名", k, v))
    seen = set()
    for k, v in by_size.items():
        if len(v) > 1:
            names = set(x["norm"] for x in v)
            if len(names) == 1:
                continue  # 已在同名里
            groups.append(("同大小", "", v))

    # 对候选组算哈希，确认真重复
    confirmed, suspected = [], []
    hashed = {}
    for kind, key, v in groups:
        hs = defaultdict(list)
        for r in v:
            if r["path"] not in hashed:
                try:
                    hashed[r["path"]] = md5(r["path"])
                except OSError:
                    hashed[r["path"]] = None
            h = hashed[r["path"]]
            if h:
                hs[h].append(r)
        for h, same in hs.items():
            if len(same) > 1:
                confirmed.append((kind, same))
        # 名字像但哈希不同 = 不同版本，留给人工
        if len(hs) > 1 and kind == "同名":
            suspected.append((kind, v))

    print("\n== 完全重复（哈希一致，可安全删多余）%d 组 ==" % len(confirmed))
    waste = 0
    for kind, same in confirmed:
        same.sort(key=lambda r: -r["size"])
        waste += sum(r["size"] for r in same[1:])
        print("   [%s] %s" % (kind, same[0]["文件名"][:52]))
        for r in same[1:]:
            print("       删 → %s" % r["相对路径"][:70])
    print("   可回收约 %.0f MB" % waste)

    print("\n== 同名但内容不同（不同版本/不同译本）%d 组 ==" % len(suspected))
    for kind, v in suspected[:12]:
        print("   %s" % v[0]["文件名"][:52])
        for r in v:
            print("       %6.1fMB  %s" % (r["size"], r["相对路径"][:66]))

    # --- 疑似无价值 ---
    junk = [r for r in rows if "文学·小说" in r["cats"]]
    print("\n== 文学/小说类 %d 个（要删的请勾）==" % len(junk))
    for r in junk[:40]:
        print("   %7.1fMB  %s" % (r["size"], r["文件名"][:62]))

    # --- 落盘 ---
    p = os.path.join(OUT, "重复与待删.csv")
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["类型", "判定", "文件名", "大小MB", "相对路径", "建议"])
        for kind, same in confirmed:
            same.sort(key=lambda r: -r["size"])
            for i, r in enumerate(same):
                w.writerow([kind, "哈希一致", r["文件名"], r["size"], r["相对路径"],
                            "保留" if i == 0 else "可删"])
        for kind, v in suspected:
            for r in v:
                w.writerow([kind, "同名不同版本", r["文件名"], r["size"], r["相对路径"], "人工决定"])
    print("\n已写：", p)
    print("统计：书 %d 个 / %.1f GB" % (len(rows), sum(r["size"] for r in rows) / 1024))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
