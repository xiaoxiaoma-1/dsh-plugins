# -*- coding: utf-8 -*-
"""删「纯权谋故事拼凑」+「鸡汤厚黑拼凑」。

双重条件，避免误伤：
  权谋类：书名含 权谋/厚黑/帝王/谋略/智谋/厚结 且 判词含 汇编/故事/堆砌/零散/拼凑
  鸡汤类：书名命中明确的鸡汤厚黑特征词
白名单：古籍原典、经典、一手经验，一律不动
"""
import argparse
import io
import json
import os
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"

# 白名单（书名含这些，绝不删）
KEEP = [
    "鬼谷子全集", "长短经", "权谋书_（汉）刘向", "天下无谋之秘卷八书--",
    "权谋高手李鸿章", "世界商战权谋", "兵家权谋", "黄石公素书", "鬼谷子破局术",
    "反经", "罗织经", "人性的弱点", "权力的48", "异类", "金钱心理学",
    "华杉", "传习录", "王阳明佛教观", "债券市场", "资本市场", "HTML5",
    "自己的MBA", "超级IP", "共享经济", "技术元素", "股票作手", "高敏感",
    "佐藤可士和", "丑小鸭", "芒格", "创业时,我们在知乎", "微表情", "新管理哲学",
    "证券交易之道", "石开投资", "转折生命力", "老A回忆录", "非理性繁荣",
    "大败局", "参与感", "增长黑客", "非同寻常的大众幻想", "周鸿祎", "实体店109套",
    "有效的广告创意", "创造性思维36计", "江恩", "图解选股", "证券投资学",
    "当代广告学", "三联生活周刊", "顶级配色", "侦查者思维", "破茧成蝶",
    "Diary of a CEO", "The Pathless Path", "不要相信你的每一个念头",
    "金钱", "价值百万的网络营销", "网络营销实战密码", "6", "9",
    # 古籍原典（不是故事拼凑，删了找不回）
    "权谋菜根谭", "权谋书_（明）张居正", "权谋残卷_张居正", "度心术",
    "官经", "每天读点", "权谋名著", "人物志", "康熙政要", "素书", "挺经", "守弱学",
]

# 权谋类：书名特征
QM_BOOK = ["权谋", "厚黑", "帝王", "谋略", "智谋", "厚结", "权术", "帝王心术"]
# 判词特征（说它是汇编/拼凑）
QM_WHY = ["汇编", "故事集", "故事堆砌", "故事拼凑", "案例堆砌", "案例拼凑",
          "拼凑", "零散", "浅显", "故事会"]

# 鸡汤类：书名特征（明确就是鸡汤/成功学/厚黑速成）
JL_BOOK = [
    "强者思想语录", "强势文化", "开窍开悟开智", "有钱人的共识", "奸的好人系列",
    "李嘉诚财智人生", "破圈开悟手册", "出位——", "极端自我就是王",
    "厚黑学处世经", "厚黑管人", "厚黑学之厚结", "厚黑无形的待友学",
    "做好领导的六件事", "新商经之", "女人要比男人更狠", "管人必备的权谋术",
    "送礼的艺术", "六万字建议", "别被情绪算计了", "成功人士战胜疲劳",
    "迅速建立强大无比的心理素质", "做人潇洒", "制服小人术",
    "世界很喧嚣", "爱的智慧,决定女人的一生", "老A精讲职场", "黑学处世经",
    "厚结人缘的处事经",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = c.execute("""select k.book_id, b.title, b.pages, k.verdict, k.gist, k.why
                        from book_card k join books b on b.id=k.book_id
                        where k.verdict in ('翻翻','跳过')""").fetchall()

    hits = []
    for r in rows:
        t = r["title"] or ""
        if any(k in t for k in KEEP):
            continue
        w = (r["why"] or "") + " " + (r["gist"] or "")
        why = ""
        if any(k in t for k in JL_BOOK):
            why = "鸡汤厚黑"
        elif any(k in t for k in QM_BOOK) and any(k in w for k in QM_WHY):
            why = "权谋故事汇编"
        if why:
            hits.append((r, why))

    print("=" * 68)
    print("将删 %d 本\n" % len(hits))
    for kind in ("权谋故事汇编", "鸡汤厚黑"):
        sub = [(r, k) for r, k in hits if k == kind]
        print("【%s】%d 本" % (kind, len(sub)))
        for r, _ in sub:
            print("  %4s页 | %-36s | %s" % (r["pages"] or "?", (r["title"] or "")[:36], (r["why"] or "")[:38]))
        print()

    if not a.go:
        print("（dry 模式。加 --go 执行）")
        return

    bak = r"E:\desktop\media\_deleted_qm_%s.json" % time.strftime("%Y%m%d_%H%M%S")
    payload = {"books": [], "chunks": [], "cards": []}
    ids = [r["book_id"] for r, _ in hits]
    for bid in ids:
        br = c.execute("select * from books where id=?", (bid,)).fetchone()
        if br:
            payload["books"].append(dict(br))
        for x in c.execute("select * from book_chunks where book_id=?", (bid,)):
            payload["chunks"].append(dict(x))
        for x in c.execute("select * from book_card where book_id=?", (bid,)):
            payload["cards"].append(dict(x))
    with open(bak, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print("已备份: %s（%d 本书 / %d 块 / %d 卡）" % (
        bak, len(payload["books"]), len(payload["chunks"]), len(payload["cards"])))

    for bid in ids:
        c.execute("delete from book_chunks where book_id=?", (bid,))
        c.execute("delete from book_card where book_id=?", (bid,))
        for tb in ("book_quality", "book_classify", "book_labels", "book_metric", "book_topics"):
            try:
                c.execute("delete from %s where book_id=?" % tb, (bid,))
            except Exception:
                pass
        c.execute("delete from books where id=?", (bid,))
    c.commit()

    # 删文件（严格：只认精确相等 或 长前缀）
    deleted = []
    titles = [(r["title"] or "") for r, _ in hits]
    for d in (r"E:\wengao", r"E:\wengao_md", r"E:\wengao_ocr"):
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            stem = os.path.splitext(name)[0]
            if not any(stem == t or (len(stem) > 10 and t.startswith(stem)) for t in titles):
                continue
            try:
                os.remove(os.path.join(d, name))
                deleted.append(name)
            except Exception:
                pass
    payload["files"] = deleted
    with open(bak, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print("\n完成：删 %d 本 / %d 个文件" % (len(ids), len(deleted)))
    print("书库: %d 本 / %d 块 / %d 卡" % (
        c.execute("select count(*) from books").fetchone()[0],
        c.execute("select count(*) from book_chunks").fetchone()[0],
        c.execute("select count(*) from book_card").fetchone()[0]))
    c.close()


if __name__ == "__main__":
    main()
