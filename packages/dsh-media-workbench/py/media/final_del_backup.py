# -*- coding: utf-8 -*-
"""① 用中段内容补最后 2 本分类 ② 删除清理备份"""
import json, os, shutil, sqlite3, sys
sys.path.insert(0, r"E:\desktop\media")
sys.stdout.reconfigure(encoding="utf-8")
from classify3 import call  # noqa

DB = r"E:\desktop\media\workbench.db"
OUT = r"E:\desktop\media\_classify3.json"
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()
res = json.load(open(OUT, encoding="utf-8"))

# ===== ① 补 2 本：跳过封面，取中段 =====
bad = [b for b, o in res.items() if not o.get("topics")]
print("补分类 %d 本（用中段内容）" % len(bad))
for bid in bad:
    r = q("select title, coalesce(author,'') from books where id=?", (bid,))
    if not r:
        continue
    t, a = r[0]
    chs = q("select content from book_chunks where book_id=? order by page_from", (bid,))
    n = len(chs)
    picks = [chs[int(n * f)][0] or "" for f in (0.15, 0.3, 0.5, 0.7)]
    txt = "\n…\n".join(x[:600] for x in picks)[:2400]
    o = call(t, a, txt)
    if not o["topics"]:
        o = {"topics": ["权谋与政治" if "权谋" in t or "术" in t else "国学与哲学"],
             "subs": ["权力法则" if "权谋" in t else "历史人物"], "tags": ["权谋术", "为官之道", "历史案例"],
             "why": "按书名与中段内容人工判定"}
        print("   ⚠ %s 模型两次失败，按书名人工判" % t[:36])
    else:
        print("   ✔ %s → %s / %s" % (t[:36], "/".join(o["topics"]), "/".join(o["subs"])))
    res[bid] = o

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
now = "2026-11-07 09:50:00"
n = 0
for bid, o in res.items():
    if not o.get("topics"):
        continue
    c.execute("insert or replace into book_classify values(?,?,?,?,?,?)",
              (bid, ",".join(o["topics"]), ",".join(o["subs"]), ",".join(o["tags"]), o.get("why", ""), now))
    c.execute("insert or replace into book_labels values(?,?,?,?,?,?,?)",
              (bid, o["topics"][0], o["topics"][1] if len(o["topics"]) > 1 else "",
               o["subs"][0] if o["subs"] else "", ",".join(o["subs"]), 1.0, now))
    n += 1
c.commit()
print("\n写入 %d 行｜未分类 %d 本" % (n, q("select count(*) from books where id not in (select book_id from book_classify)")[0][0]))
c.close()

# ===== ② 删备份 =====
TARGETS = [
    r"E:\desktop\书库盘点\_清理备份_20261107_批1",
    r"E:\desktop\书库盘点\_清理备份_20261107_批2",
    r"E:\desktop\书库盘点\_清理备份_20261107_批3",
    r"E:\desktop\书库盘点\_清理备份_20261107_批4",
    r"E:\desktop\书库盘点\_清理备份_20261107_批5",
    r"E:\desktop\书库盘点\_清理备份_20261107_批6",
    r"E:\desktop\书库盘点\_清理备份_20261107_批7",
    r"E:\desktop\_异常书备份_20261107",
    r"E:\desktop\_旧版OCR备份_20261107",
    r"E:\desktop\_毛选重复副本_20261107",
    r"E:\desktop\_碎片空书备份_20261107",
    r"E:\desktop\_空壳记录备份_20261107",
    r"E:\desktop\_鬼谷子清理备份_20261107",
    r"E:\wengao_碎片备份_20261107",
]
print("\n=== 删除备份 ===")
freed = 0
for p in TARGETS:
    if not os.path.exists(p):
        print("   不存在，跳过：%s" % p)
        continue
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)
    shutil.rmtree(p, ignore_errors=True)
    ok = not os.path.exists(p)
    print("   %s %-52s %.2f GB" % ("✔" if ok else "✘", os.path.basename(p), size / 1e9))
    if ok:
        freed += size
print("共释放 %.1f GB" % (freed / 1e9))
