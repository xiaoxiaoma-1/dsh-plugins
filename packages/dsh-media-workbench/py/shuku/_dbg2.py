# -*- coding: utf-8 -*-
import json
import re
import sqlite3
import sys

sys.path.insert(0, r"E:\desktop\书库盘点")
import extract_split as E

c = sqlite3.connect(E.DB)
row = c.execute(
    "select c.id, b.title, c.content from book_chunks c join books b on b.id=c.book_id "
    "where length(c.content) > 300 limit 1").fetchone()
c.close()

raw = E.call("书名：《%s》\n\n段落：\n%s" % (row[1][:40], row[2][:1200]))
t = raw.strip()
t2 = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
m = re.search(r"\[.*\]", t2, re.S)
print("有匹配:", bool(m))
if m:
    s = m.group(0)
    print("片段长度:", len(s))
    print("首尾:", repr(s[:80]), "...", repr(s[-80:]))
    try:
        arr = json.loads(s)
        print("解析成功:", len(arr))
    except Exception as e:
        print("json 错误:", e)
        pos = getattr(e, "pos", None)
        if pos:
            print("出错位置上下文:", repr(s[max(0, pos - 60):pos + 60]))
