# -*- coding: utf-8 -*-
import glob, os, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
print("=== 所有表 ===")
tabs = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
print("  ", ", ".join(tabs))

print("\n=== 找 '面坨' 出现在任何表的任何文本字段 ===")
hits = 0
for t in tabs:
    try:
        cols = [r[1] for r in c.execute("pragma table_info(%s)" % t)]
    except Exception:
        continue
    for col in cols:
        try:
            n = c.execute("select count(*) from %s where cast(%s as text) like '%%面坨%%'" % (t, col)).fetchone()[0]
            if n:
                print("   %s.%s: %d 条" % (t, col, n))
                hits += 1
        except Exception:
            pass
if not hits:
    print("   全库没有'面坨'")

print("\n=== douyin 目录/文件（可能存了私信抓取）===")
for d in [r"E:\tools\asr\out", r"E:\desktop\media", r"E:\desktop\media\_condense"]:
    if not os.path.isdir(d):
        continue
    fs = [f for f in os.listdir(d) if "面" in f or "dm" in f.lower() or "私" in f]
    if fs:
        print("   %s: %s" % (d, fs[:10]))

print("\n=== 昨天(11-06)转写的 txt（按时间）===")
rows = []
for f in glob.glob(r"E:\tools\asr\out\*.txt"):
    st = os.path.getmtime(f)
    rows.append((st, f))
rows.sort(reverse=True)
import time
for st, f in rows[:12]:
    print("   %s  %s" % (time.strftime("%m-%d %H:%M", time.localtime(st)), os.path.basename(f)))
c.close()
