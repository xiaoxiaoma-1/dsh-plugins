# -*- coding: utf-8 -*-
"""批6：清残余小说 + 清残余重复"""
import json, os, re, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BAK = r"E:\desktop\书库盘点\_清理备份_20261107_批6"
os.makedirs(BAK, exist_ok=True)
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()

# ============ ① 小说（保留王阳明两本 + 苏菲的世界）============
FICTION_DEL = [
    "33-绿色国王", "在细雨中呼喊", "奸的好人系列19-《心锚》", "将心权谋", "暗夜与黎明",
    "朱棣的权谋", "权谋 权谋之业", "权谋_（英）罗伯特·哈利斯", "权谋之业_（英）哈里斯",
    "牧羊少年奇幻之旅", "秘密规则－－股市职业炒盘手自述", "豆豆三部曲2《遥远的救世主》",
    "遥远的救世主（豆豆著）", "较量  中国式权谋VS日本式经营", "阳光下的权谋", "阳谋高手",
    "陈峻菁女性权谋三部曲", "陷阱  周旋于官场陷阱",
]
KEEP = ["王阳明：全三册", "王阳明：让良知自由", "苏菲的世界"]

novel_ids = []
for kw in FICTION_DEL:
    rs = q("select id, title from books where title like ?", ("%" + kw + "%",))
    for bid, t in rs:
        if any(k in t for k in KEEP):
            continue
        if bid not in [x[0] for x in novel_ids]:
            novel_ids.append((bid, t))
print("要删的小说 %d 本：" % len(novel_ids))
for _, t in novel_ids:
    print("   ", t[:52])

# ============ ② 残余重复 ============
DUP_GROUPS = [
    ("权谋之业", "权谋之业_（英）哈里斯著"),          # 保留
    ("遥远的救世主", "豆豆三部曲2《遥远的救世主》"),
    ("说三国话权谋", "说三国话权谋_李炳彦"),
    ("立威篇", "5立威篇立威篇"),
    ("老A回忆录", "老A回忆录(用字处理软件打印)"),
    ("资本论", "038〔德〕卡尔·马克思著"),
]
dup_ids = []
for kw, keep_kw in DUP_GROUPS:
    rs = q("select id, title, (select coalesce(sum(length(content)),0) from book_chunks where book_id=b.id) n from books b where title like ?", ("%" + kw + "%",))
    if len(rs) < 2:
        continue
    keep = [x for x in rs if keep_kw in x[1]]
    keepid = keep[0][0] if keep else max(rs, key=lambda x: x[2])[0]
    for bid, t, n in rs:
        if bid == keepid or any(k in t for k in KEEP):
            continue
        if bid not in [x[0] for x in dup_ids]:
            dup_ids.append((bid, t, n))
print("\n要删的重复 %d 本：" % len(dup_ids))
for _, t, n in dup_ids:
    print("   %s字 %s" % (n, t[:50]))

allids = list({b for b, _ in novel_ids} | {b for b, _, _ in dup_ids})
print("\n合计 %d 本" % len(allids))

# 备份正文
exp = {}
for bid in allids:
    t = q("select title from books where id=?", (bid,))[0][0]
    exp[bid] = {"title": t, "chunks": [[p, x] for p, x in q(
        "select page_from, content from book_chunks where book_id=?", (bid,))]}
json.dump(exp, open(os.path.join(BAK, "待删正文.json"), "w", encoding="utf-8"), ensure_ascii=False)

ph = ",".join("?" * len(allids))
tabs = [r[0] for r in q("select name from sqlite_master where type='table'")
        if any(col[1] == "book_id" for col in c.execute("pragma table_info(%s)" % r[0]))]
for tb in tabs:
    c.execute("delete from %s where book_id in (%s)" % (tb, ph), allids)
c.execute("delete from books where id in (%s)" % ph, allids)
c.commit()
print("\n现库：%d 本 / %d 块 / %d 字" % (
    q("select count(*) from books")[0][0], q("select count(*) from book_chunks")[0][0],
    q("select sum(length(content)) from book_chunks")[0][0]))
c.close()
