# -*- coding: utf-8 -*-
import re, sqlite3, sys
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()

print("=== ① 直播：段 vs 场 ===")
print("live_segments 总段数:", q("select count(*) from live_segments")[0][0])
rows = q("select id, post_id, author, seg_no, text, created_at from live_segments")
# 按 post_id 分组算场次
by_post = defaultdict(list)
for sid, pid, au, seg, txt, ca in rows:
    by_post[pid].append((sid, au, seg, len(txt or "")))
print("不同 post_id（推测=场次）:", len(by_post))
print("\n按 post_id 前 12 场：")
for pid, segs in sorted(by_post.items(), key=lambda x: -len(x[1]))[:12]:
    au = segs[0][1]
    print("   %-22s %s：%d 段 / %d 字" % (pid, (au or '?')[:14], len(segs), sum(s[3] for s in segs)))

# 看 posts 表里的直播场次
print("\nposts 表 kind='live' 的条目（每场一条？）:")
for r in q("select id, author, date, substr(text,1,60) from posts where kind='live' limit 8"):
    print("   id=%s | %s | %s" % (r[0], (r[1] or '')[:40], (r[3] or '').replace('\n', ' ')[:50]))
print("posts kind=live 总数:", q("select count(*) from posts where kind='live'")[0][0])

print()
print("=== ② 抖音文案近 7 天为什么比总数多 ===")
print("posts 按 kind + 近7天:")
for r in q("""select coalesce(kind,'(空)'), count(*),
                     sum(case when created_at >= date('now','-7 day') then 1 else 0 end)
              from posts group by kind"""):
    print("   %-10s 总 %5d | 近7天 %4d" % (r[0], r[1], r[2]))
print("posts 全表近 7 天:", q("select count(*) from posts where created_at >= date('now','-7 day')")[0][0])
print("live_segments 近 7 天:", q("select count(*) from live_segments where created_at >= date('now','-7 day')")[0][0])

print()
print("=== ③ 推文 vs 抖音文案，是谁的 ===")
print("posts 按 author + kind:")
for r in q("""select coalesce(author,'(空)') a, coalesce(kind,'(空)') k, count(*) n
              from posts group by a, k order by n desc limit 15"""):
    print("   %-32s %-10s %5d" % (r[0][:32], r[1], r[2]))
print()
print("抽 3 条 kind='主贴' 看是什么:")
for r in q("select id, author, date, substr(text,1,100) from posts where kind='主贴' limit 3"):
    print("   %s | %s | %s | %s" % (r[0], (r[1] or '')[:20], r[2], (r[3] or '').replace('\n', ' ')[:80]))
print()
print("抽 3 条 kind='douyin' 看是什么:")
for r in q("select id, author, date, substr(text,1,100) from posts where kind='douyin' limit 3"):
    print("   %s | %s | %s | %s" % (r[0], (r[1] or '')[:20], r[2], (r[3] or '').replace('\n', ' ')[:80]))
c.close()
