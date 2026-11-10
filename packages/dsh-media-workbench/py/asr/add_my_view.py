# -*- coding: utf-8 -*-
"""把用户的口述原话 + AI 优化完整版，各写一条进 my_views。"""
import io
import json
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"

RAW = """其实我觉得年轻的时候如果说你不去搞钱，你不去认认真真搞钱，不要听信那些所谓的什么「我很年轻的时候就是拿来享受」。不然的话，你老了之后，你再去想想要去享受，你会发现好多你年轻的时候想要的东西，其实你根本就没有办法享受到了。

我觉得这根本就是一个歪理啊。为什么这样说？因为如果说你年轻的时候不去搞钱的话，你不去努力地挣钱的话，你可能甚至活不到能够享受的那一天，对吧？你年轻的时候不去搞钱的话，你可能到 30 岁、40 岁你甚至没有钱出去玩。到那个时候你再想去赚钱，想要去怎么怎么样，你会发现你往前推十多二十年，你 20 多岁的时候好像也没有享受到什么东西，无非就是开开心心地过了 10 年。但当你 30 岁、40 岁的时候，你会发现你没有什么钱，你没什么资本，你也没什么资格来享乐。"""

POLISHED = """我听过一句很流行的话：年轻的时候要享受，别把青春都拿去挣钱。

这句话的问题在于，它默认享受不需要资格。实际上享受要三样东西同时到手：身体、钱、时间。20 多岁你只占了一样，就是身体。这时候所谓的享受，其实是用很低的钱买来的自由——去几个地方、吃几顿好的、玩到凌晨也不累。它不叫享受，叫消耗。

真正能谈享受的年纪，是三样齐了的时候。所以年轻时去搞钱，不是压抑自己，是为了 30 岁、40 岁真的能享受。

反过来，如果年轻时不去搞，30 岁、40 岁会发现自己没资本、没资格享乐，而且这时候再想挣，成本和难度都翻倍。往回看那十几年，就是开开心心过了十年，没留下任何能积累的东西。

最狠的一句：年轻时不搞钱，你可能根本活不到能享受的那一天。"""


def main():
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    ts = int(time.time())
    rows = [
        {
            "id": f"mv_{ts}_raw",
            "kind": "原话",
            "topic_id": None,
            "title": "年轻的时候不认真搞钱，你可能活不到能享受的那天（原话）",
            "content": RAW,
            "ai_review": "未做任何措辞修改，只整理了标点和分段。这是原始口述。",
            "status": "active",
            "tags": "年轻,搞钱,享受,原话,反鸡汤",
        },
        {
            "id": f"mv_{ts}_ai",
            "kind": "金句",
            "topic_id": None,
            "title": "「年轻就该享受」是让未来的自己买单（AI 优化完整版）",
            "content": POLISHED,
            "ai_review": "在用户原话的骨架上重排三段式；新增框架「享受要身体/钱/时间三样同时到手」，把感受问题转成资格条件问题。原话的三句锋刃全部保留。",
            "status": "active",
            "tags": "年轻,搞钱,享受,AI优化,可发",
        },
    ]
    c = sqlite3.connect(DB)
    for r in rows:
        c.execute(
            "insert into my_views (id,kind,topic_id,title,content,chars,ai_review,status,tags,created_at,updated_at)"
            " values (?,?,?,?,?,?,?,?,?,?,?)",
            (r["id"], r["kind"], r["topic_id"], r["title"], r["content"],
             len(r["content"]), r["ai_review"], r["status"], r["tags"], now, now),
        )
    c.commit()
    out = []
    for row in c.execute("select id,kind,title,chars,status from my_views order by created_at"):
        out.append({"id": row[0], "kind": row[1], "title": row[2], "chars": row[3], "status": row[4]})
    print(json.dumps({"ok": True, "count": len(out), "rows": out}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
