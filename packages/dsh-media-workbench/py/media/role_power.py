# -*- coding: utf-8 -*-
"""按圆桌角色盘点素材弹药：每个大类/子类有多少书、多少文案、多少字、多少标签"""
import json, sqlite3, sys
from collections import Counter, defaultdict
sys.path.insert(0, r"E:\desktop\media")
from classify3 import TREE  # noqa
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()

o = ["=== 圆桌角色素材弹药盘点 ===\n"]
rows = []
for topic, subs in TREE.items():
    # 书
    bs = q("""select b.id, b.title, cc.subs, cc.tags,
                     (select coalesce(sum(length(content)),0) from book_chunks where book_id=b.id) n
              from book_classify cc join books b on b.id=cc.book_id
              where cc.topics like ?""", ("%" + topic + "%",))
    # 文案
    ps = q("""select pc.src_id, pc.subs, pc.tags from post_classify pc where pc.topics like ?""",
           ("%" + topic + "%",))
    bchars = sum(x[4] for x in bs)
    # 子类覆盖
    sub_cnt = Counter()
    for r in bs:
        for s in (r[2] or "").split(","):
            if s:
                sub_cnt[s] += 1
    for r in ps:
        for s in (r[1] or "").split(","):
            if s:
                sub_cnt[s] += 1
    own_sub = [s for s in subs if sub_cnt[s] > 0]
    empty_sub = [s for s in subs if sub_cnt[s] == 0]
    tag_cnt = Counter()
    for r in bs:
        for t in (r[3] or "").split(","):
            if t:
                tag_cnt[t] += 1
    for r in ps:
        for t in (r[2] or "").split(","):
            if t:
                tag_cnt[t] += 1
    rows.append({
        "topic": topic, "books": len(bs), "posts": len(ps), "chars": bchars,
        "subs_used": len(own_sub), "subs_total": len(subs), "empty": empty_sub,
        "tags": len(tag_cnt), "tag_top": tag_cnt.most_common(6),
        "sub_cnt": sub_cnt,
    })

o.append("%-10s %6s %6s %10s %8s %8s" % ("大类", "书", "文案", "书字数", "子类用到", "标签数"))
for r in rows:
    o.append("%-10s %6d %6d %10d %6s %8d" % (
        r["topic"], r["books"], r["posts"], r["chars"],
        "%d/%d" % (r["subs_used"], r["subs_total"]), r["tags"]))

o.append("\n=== 各角色细节 ===")
for r in rows:
    o.append("\n【%s】书 %d 本 / 文案 %d 条 / 书字数 %d 万 / 标签 %d 个" % (
        r["topic"], r["books"], r["posts"], r["chars"] // 10000, r["tags"]))
    o.append("   子类弹药（前 12）：%s" % ", ".join(
        "%s %d" % (k, v) for k, v in r["sub_cnt"].most_common(12)))
    if r["empty"]:
        o.append("   ⚠ 没素材的子类：%s" % ", ".join(r["empty"]))
    o.append("   标签示例：%s" % "、".join(x[0] for x in r["tag_top"]))

# 全库合计
tb = q("select count(*) from books")[0][0]
tp = q("select count(*) from post_classify")[0][0]
tc = q("select coalesce(sum(length(content)),0) from book_chunks")[0][0]
tpc = q("select coalesce(sum(length(text)),0) from posts")[0][0]
o.append("\n=== 全库合计 ===")
o.append("书 %d 本 / %.2f 亿字｜文案 %d 条 / %.0f 万字" % (tb, tc / 1e8, tp, tpc / 1e4))
open(r"E:\desktop\media\_role_power.txt", "w", encoding="utf-8").write("\n".join(str(x) for x in o))
print("\n".join(str(x) for x in o[:12]))
