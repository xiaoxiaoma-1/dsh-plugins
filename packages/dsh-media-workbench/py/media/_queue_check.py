# -*- coding: utf-8 -*-
import sqlite3, sys, os, glob
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()

print("=== posts 按 kind 统计 ===")
for r in q("""select coalesce(kind,'(空)') k, count(*) n,
                     sum(length(coalesce(text,''))) ch,
                     sum(case when length(coalesce(text,''))<50 then 1 else 0 end) empty
              from posts group by kind order by n desc"""):
    print("   kind=%-12s %5d 条 | %9d 字 | 空/极少 %d" % (r[0], r[1], r[2] or 0, r[3]))

print()
print("=== live_segments ===")
print("   %d 段 / %d 字" % (q("select count(*), sum(chars) from live_segments")[0]))
for r in q("select coalesce(author,'?'), count(*), sum(chars) from live_segments group by author order by 2 desc limit 6"):
    print("   %-20s %3d 段 %8d 字" % (r[0][:20], r[1], r[2] or 0))

print()
print("=== 待转写/转写中间文件 ===")
for d in [r"E:\tools\asr\out", r"E:\desktop\media", r"E:\tools\asr"]:
    if not os.path.isdir(d):
        continue
    for pat in ("*.wav", "*.txt", "*.json", "*queue*", "*pending*"):
        fs = glob.glob(os.path.join(d, pat))
        if fs and len(fs) < 200:
            print("   %s\\%s → %d 个" % (d, pat, len(fs)))
        elif fs:
            print("   %s\\%s → %d 个（省略）" % (d, pat, len(fs)))
print()
print("=== 直播相关表 ===")
for r in q("""select name from sqlite_master where type='table' and (name like '%live%' or name like '%stream%')"""):
    print("   ", r[0], q("select count(*) from %s" % r[0])[0][0], "行")
c.close()
