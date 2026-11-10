# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s: c.execute(s).fetchall()
print("== tok 列样例 ==")
for r in q("select rowid, substr(tok,1,120) from chunks_fts limit 5"):
    print("  rowid=%s tok=%s" % (r[0], r[1]))
print()
print("== 试 match tok 里的词 ==")
for kw in ["权力", "王阳明", "知行合一", "毛"]:
    try:
        n = q("select count(*) from chunks_fts where tok match '%s'" % kw)[0][0]
        print("  tok match '%s' -> %d" % (kw, n))
    except Exception as e:
        print("  tok match '%s' 失败: %s" % (kw, e))
print()
print("== 试前缀查询 ==")
for expr in ["权力*", "王阳明*", "知行合一*"]:
    try:
        n = q("select count(*) from chunks_fts where tok match '%s'" % expr)[0][0]
        print("  tok match '%s' -> %d" % (expr, n))
    except Exception as e:
        print("  '%s' 失败: %s" % (expr, e))
print()
print("== LIKE 兜底测试 ==")
for kw in ["权力", "王阳明"]:
    n = q("select count(*) from book_chunks where content like '%%%s%%'" % kw)[0][0]
    print("  LIKE %%%s%% -> %d 条" % (kw, n))
