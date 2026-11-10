import json, os, sqlite3, sys, time

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BACKUP = r"E:\desktop\media\_deleted_booklist_20261106.json"

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cur = c.cursor()

# 只删「书单卡」：kind='book' 且 author='书单' 且 date='2026-10-30'
rows = cur.execute(
    "select * from posts where kind='book' and author='书单' and date='2026-10-30'"
).fetchall()
ids = [r["id"] for r in rows]
print(f"命中 {len(ids)} 条（kind=book / author=书单 / date=2026-10-30）")
if not ids:
    print("没有命中，退出")
    sys.exit(0)

# 1) 先备份整行
with open(BACKUP, "w", encoding="utf-8") as f:
    json.dump([dict(r) for r in rows], f, ensure_ascii=False, indent=1)
print("已备份 ->", BACKUP, os.path.getsize(BACKUP) // 1024, "KB")

# 2) 统计依赖
q = ",".join("?" * len(ids))
deps = {}
for t in ["split_items", "atoms", "hooks", "post_sources", "ideas"]:
    try:
        cols = [d[1] for d in cur.execute(f"pragma table_info({t})")]
        key = "post_id" if "post_id" in cols else ("source_id" if "source_id" in cols else None)
        if not key:
            deps[t] = "无关联字段"
            continue
        n = cur.execute(f"select count(*) from {t} where {key} in ({q})", ids).fetchone()[0]
        deps[t] = n
    except Exception as e:
        deps[t] = f"err {e}"
print("依赖：", deps)

# 3) 删依赖（只删指向这些 post 的）
# 记忆里说：垃圾真删不留 hidden；数据要清干净，不留孤儿
for t, key in [("split_items", "post_id"), ("atoms", "post_id"), ("hooks", "post_id"),
               ("post_sources", "source_id"), ("ideas", "post_id")]:
    try:
        cols = [d[1] for d in cur.execute(f"pragma table_info({t})")]
        if key not in cols:
            continue
        n = cur.execute(f"delete from {t} where {key} in ({q})", ids).rowcount
        print(f"  清 {t}: {n} 行")
    except Exception as e:
        print(f"  清 {t} 失败: {e}")

# 4) 删 posts
n = cur.execute(f"delete from posts where id in ({q})", ids).rowcount
print(f"删 posts: {n} 行")
c.commit()

left = cur.execute("select count(*) from posts where kind='book'").fetchone()[0]
total = cur.execute("select count(*) from posts").fetchone()[0]
print(f"剩余：kind=book {left} 条 / posts 共 {total} 条")
c.close()
