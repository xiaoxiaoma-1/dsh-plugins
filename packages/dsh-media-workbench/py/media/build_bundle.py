# -*- coding: utf-8 -*-
"""把一个大类构建成一本「汇编书」：按子类分组，每本取首/中/尾核心段落"""
import json, os, sqlite3, sys
from collections import defaultdict
sys.path.insert(0, r"E:\desktop\media")
from classify3 import TREE  # noqa

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
OUTDIR = r"E:\desktop\书库盘点\_cangjie_input"
os.makedirs(OUTDIR, exist_ok=True)
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()

# 子类 → 大类 反查表
SUB2TOPIC = {}
for tp, subs in TREE.items():
    for s in subs:
        SUB2TOPIC.setdefault(s, []).append(tp)


def build(topic, excerpt_len=900):
    rows = q("""select b.id, b.title, coalesce(b.author,''), cc.subs
                from book_classify cc join books b on b.id=cc.book_id
                where cc.topics like ?""", ("%" + topic + "%",))
    own_subs = set(TREE.get(topic, []))
    print("《%s》共 %d 本（该大类专属子类 %d 个）" % (topic, len(rows), len(own_subs)))
    by_sub = defaultdict(list)
    for bid, t, a, subs in rows:
        mine = [s for s in (subs or "").split(",") if s in own_subs]
        first = mine[0] if mine else "跨类书目"
        by_sub[first].append((bid, t, a))

    parts = ["# 《%s》大类汇编\n\n本汇编把书库里「%s」大类下的 %d 本书，按子类分组、每本摘取首/中/尾核心段落汇编而成，作为蒸馏素材。\n" % (topic, topic, len(rows))]
    total = 0
    for sub, items in sorted(by_sub.items(), key=lambda x: -len(x[1])):
        parts.append("\n\n## 子类：%s（%d 本）\n" % (sub, len(items)))
        for bid, t, a in sorted(items):
            chs = q("select content from book_chunks where book_id=? order by page_from", (bid,))
            texts = [x[0] or "" for x in chs]
            if not texts:
                continue
            n = len(texts)
            picks = [texts[0], texts[n // 2] if n > 2 else "", texts[n - 1]]
            ex = "\n…\n".join(x[:excerpt_len] for x in picks if x)
            parts.append("\n### 《%s》%s\n" % (t, ("／" + a) if a else ""))
            parts.append(ex + "\n")
            total += len(ex)
    txt = "".join(parts)
    fn = os.path.join(OUTDIR, "%s.md" % topic.replace("/", "_"))
    open(fn, "w", encoding="utf-8").write(txt)
    print("   汇编 %d 字 → %s" % (len(txt), fn))
    subs = {k: len(v) for k, v in sorted(by_sub.items(), key=lambda x: -len(x[1]))}
    print("   子类分布:", subs)
    return fn, len(txt), len(rows), subs


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "内容创作"
    build(topic)
