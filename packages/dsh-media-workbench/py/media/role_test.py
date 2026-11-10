# -*- coding: utf-8 -*-
"""实测：拿一个真实问题，看每个角色能捞出多少可用素材"""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()

QUESTION = "30岁从体制内出来做自媒体，第一步该干什么"
KEYWORDS = {
    "转型": '"转 型"', "体制内": '"体 制 内"', "第一份": '"第 一"',
    "起步": '"起 步"', "副业": '"副 业"', "定位": '"定 位"',
}
TOPICS = ["权谋与政治", "商业与变现", "内容创作", "心理与人性", "语言与思维",
          "AI 与工具", "国学与哲学", "身心与生活"]

o = ["=== 实测：一个问题下每个角色的弹药量 ==="]
o.append("问题：%s\n" % QUESTION)
for t in TOPICS:
    o.append("\n【%s】" % t)
    for kw, expr in KEYWORDS.items():
        nb = q("""select count(*) from chunks_fts f join book_classify bc on bc.book_id=f.book_id
                  where f.tok match ? and bc.topics like ?""", (expr, "%" + t + "%"))[0][0]
        np_ = q("""select count(*) from posts p join post_classify pc on pc.src_id='post:'||p.id
                   where pc.topics like ? and p.text like ?""", ("%" + t + "%", "%" + kw + "%"))[0][0]
        o.append("   %-6s 书里 %4d 段 | 文案 %3d 条" % (kw, nb, np_))

o.append("\n=== 各角色能拿出的代表性原文（每角色 1 条）===")
for t in TOPICS:
    r = q("""select b.title, substr(f.content,1,150) from chunks_fts f
             join book_classify bc on bc.book_id=f.book_id join books b on b.id=f.book_id
             where f.tok match '"转 型"' and bc.topics like ? limit 1""", ("%" + t + "%",))
    o.append("\n【%s】%s" % (t, (r[0][0][:30] if r else "（无命中）")))
    if r:
        o.append("   " + (r[0][1] or "").replace("\n", " ")[:150])
open(r"E:\desktop\media\_role_test.txt", "w", encoding="utf-8").write("\n".join(str(x) for x in o))
print("\n".join(str(x) for x in o[:26]))
