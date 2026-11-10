# -*- coding: utf-8 -*-
"""修正：原话条目要逐字保留，上一版擅自删了「好像往回推，」和「我不知道应该怎么说啊」。"""
import io
import json
import sqlite3
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"

RAW = """其实我觉得年轻的时候如果说你不去搞钱，你不去认认真真搞钱，不要听信那些所谓的什么「我很年轻的时候就是拿来享受」。不然的话，你老了之后，你再去想想要去享受，你会发现好多你年轻的时候想要的东西，其实你根本就没有办法享受到了。所以说，年轻的时候就是要去享受。

我觉得这根本就是一个歪理啊。为什么这样说？因为如果说你年轻的时候不去搞钱的话，你不去努力地挣钱的话，你可能甚至活不到能够享受的那一天，对吧？你年轻的时候不去搞钱的话，你可能到 30 岁、40 岁你甚至没有钱出去玩。到那个时候你再想去赚钱，想要去怎么怎么样，你会发现你好像往回推，往前推十多二十年，你 20 多岁的时候好像也没有享受到什么东西，无非就是开开心心地过了 10 年。但当你 30 岁、40 岁的时候，你会发现你没有什么钱，你没什么资本，你也没什么资格来享乐，我不知道应该怎么说啊。"""


def main():
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    c = sqlite3.connect(DB)
    row = c.execute("select id from my_views where kind='原话' order by created_at desc limit 1").fetchone()
    if not row:
        print(json.dumps({"ok": False, "error": "没找到原话条目"}, ensure_ascii=False))
        return
    c.execute(
        "update my_views set content=?, chars=?, ai_review=?, updated_at=? where id=?",
        (RAW, len(RAW), "逐字保留，只补标点和分段；没有删任何一句，包括口语里的重复和「我不知道应该怎么说啊」。", now, row[0]),
    )
    c.commit()
    out = []
    for r in c.execute("select id,kind,title,chars from my_views order by created_at"):
        out.append({"id": r[0], "kind": r[1], "title": r[2], "chars": r[3]})
    print(json.dumps({"ok": True, "rows": out, "raw_head": RAW[:60]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
