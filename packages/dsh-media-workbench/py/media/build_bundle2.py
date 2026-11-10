# -*- coding: utf-8 -*-
"""构建「书 + 抖音文案 + 直播」合并的汇编（书按子类摘首中尾，文案按子类抽样进全文）"""
import os, sqlite3, sys
from collections import defaultdict
sys.path.insert(0, r"E:\desktop\media")
from classify3 import TREE  # noqa

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
OUTDIR = r"E:\desktop\书库盘点\_cangjie_input"
os.makedirs(OUTDIR, exist_ok=True)
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()


def build(topic, per_sub_post=30, excerpt_len=900):
    own = set(TREE.get(topic, []))

    # ---- 书 ----
    books = q("""select b.id, b.title, coalesce(b.author,''), cc.subs
                 from book_classify cc join books b on b.id=cc.book_id
                 where cc.topics like ?""", ("%" + topic + "%",))
    by_sub = defaultdict(lambda: {"books": [], "posts": []})
    for bid, t, a, subs in books:
        mine = [s for s in (subs or "").split(",") if s in own]
        by_sub[mine[0] if mine else "跨类书目"]["books"].append((bid, t, a))

    # ---- 文案 / 直播 ----
    posts = q("""select pc.src_id, pc.subs, pc.tags from post_classify pc
                 where pc.topics like ?""", ("%" + topic + "%",))
    post_by_sub = defaultdict(list)
    for sid, subs, tags in posts:
        mine = [s for s in (subs or "").split(",") if s in own]
        post_by_sub[mine[0] if mine else "跨类书目"].append((sid, tags))

    parts = ["# 《%s》大类汇编（书 + 抖音文案 + 直播）\n\n"
             "本汇编把「%s」大类下的 **%d 本书** 与 **%d 条抖音文案/直播分段** 合并，"
             "按子类分组摘录，作为蒸馏素材。\n" % (topic, topic, len(books), len(posts))]
    npost = 0
    for sub, box in sorted(by_sub.items(), key=lambda x: -(len(x[1]["books"]) + len(x[1]["posts"]))):
        parts.append("\n\n## 子类：%s（书 %d 本 · 文案 %d 条）\n"
                     % (sub, len(box["books"]), len(post_by_sub.get(sub, []))))
        for bid, t, a in sorted(box["books"]):
            chs = q("select content from book_chunks where book_id=? order by page_from", (bid,))
            texts = [x[0] or "" for x in chs]
            if not texts:
                continue
            n = len(texts)
            picks = [texts[0], texts[n // 2] if n > 2 else "", texts[n - 1]]
            parts.append("\n### 书：《%s》%s\n" % (t, ("／" + a) if a else ""))
            parts.append("\n…\n".join(x[:excerpt_len] for x in picks if x) + "\n")
        plist = post_by_sub.get(sub, [])[:per_sub_post]
        for sid, tags in plist:
            if sid.startswith("post:"):
                row = q("select text from posts where id=?", (sid[5:],))
            else:
                row = q("select text from live_segments where id=?", (sid[5:],))
            if not row or not row[0][0]:
                continue
            body = row[0][0][:1400]
            parts.append("\n### 文案/直播（标签：%s）\n%s\n" % (tags or "无", body))
            npost += 1
    txt = "".join(parts)
    fn = os.path.join(OUTDIR, "%s.md" % topic.replace("/", "_"))
    open(fn, "w", encoding="utf-8").write(txt)
    print("《%s》书 %d 本 + 文案 %d 条 → 汇编 %d 字 → %s"
          % (topic, len(books), npost, len(txt), fn))
    return fn, len(txt)


if __name__ == "__main__":
    for t in (sys.argv[1:] or ["内容创作"]):
        build(t)
