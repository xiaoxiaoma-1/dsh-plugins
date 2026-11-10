# -*- coding: utf-8 -*-
import json, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
c = sqlite3.connect(r"E:\desktop\media\workbench.db")
q = lambda s, p=(): c.execute(s, p).fetchall()

print("=== 今天入库的 douyin ===")
rows = q("""select id, coalesce(author,''), length(coalesce(text,'')), created_at
            from posts where kind='douyin' and created_at >= date('now')
            order by created_at desc""")
for r in rows:
    print("  %-30s %-22s %5d字  %s" % (r[0][:30], r[1][:22], r[2], r[3]))

print("\ndouyin 总数:", q("select count(*) from posts where kind='douyin'")[0][0])
print("已分类:", q("select count(*) from post_classify where src_id like 'post:dy%'")[0][0])

print("\n=== 未分类且字数>150 的新内容 ===")
rows = q("""select p.id, length(coalesce(p.text,'')) n from posts p
            where not exists(select 1 from post_classify pc where pc.src_id = 'post:' || p.id)
              and length(coalesce(p.text,'')) > 150
            order by n desc limit 15""")
for r in rows:
    print("  ", r[0][:40], r[1], "字")

print("\n=== pipeline 输出文件 ===")
try:
    d = json.load(open(r"E:\tools\asr\out\douyin_inbox.json", encoding="utf-8"))
    print("  inbox count:", d.get("count"))
except Exception as e:
    print("  ", e)
try:
    s = json.load(open(r"E:\tools\asr\out\douyin_seen.json", encoding="utf-8"))
    print("  seen 已处理:", len(s.get("items", {})))
except Exception as e:
    print("  seen:", e)
c.close()
