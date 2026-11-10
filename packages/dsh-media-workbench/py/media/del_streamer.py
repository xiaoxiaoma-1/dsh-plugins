"""删除「军师77懂女生」的全部资料（取关 + 判断为错误关注）

范围：posts 记录及关联拆解、精简产物、录制 mp4、逐字稿、监控配置里的地址。
策略：先备份（json + 文件移到回收目录），再删；不直接抹盘。
"""
import json
import os
import re
import shutil
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
KEY = "军师77"
STAMP = time.strftime("%Y%m%d_%H%M%S")
DB = r"E:\desktop\media\workbench.db"
REC_ROOTS = [r"D:\采数据\直播录制", r"D:\采数据\逐字稿\直播录制"]
COND = r"E:\desktop\media\_condense"
RECYCLE = rf"E:\desktop\_deleted_{KEY}_{STAMP}"
BAK = rf"E:\desktop\media\_deleted_{KEY}_{STAMP}.json"

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cur = c.cursor()

rows = cur.execute("select * from posts where author like ?", (f"%{KEY}%",)).fetchall()
ids = [r["id"] for r in rows]
print(f"posts 命中 {len(ids)} 条")
for r in rows:
    print(f"  {r['id']} | {r['author']} | {len(r['text'] or '')} 字")

if ids:
    with open(BAK, "w", encoding="utf-8") as f:
        json.dump([dict(r) for r in rows], f, ensure_ascii=False, indent=1)
    print("已备份 posts ->", BAK, os.path.getsize(BAK) // 1024, "KB")

# 关联表
q = ",".join("?" * len(ids)) if ids else None
if ids:
    for t, key in [("split_items", "post_id"), ("hooks", "post_id"),
                   ("post_sources", "source_id"), ("post_split_done", "post_id")]:
        try:
            cols = [d[1] for d in cur.execute(f"pragma table_info({t})")]
            if key not in cols:
                continue
            n = cur.execute(f"delete from {t} where {key} in ({q})", ids).rowcount
            print(f"  清 {t}: {n} 行")
        except Exception as e:
            print(f"  清 {t} 跳过: {e}")
    n = cur.execute(f"delete from posts where id in ({q})", ids).rowcount
    print(f"删 posts: {n} 行")
    c.commit()
c.close()

# 文件：录制 + 逐字稿 + 精简产物
os.makedirs(RECYCLE, exist_ok=True)
moved = []
for root in REC_ROOTS:
    if not os.path.isdir(root):
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        if KEY in os.path.basename(dirpath):
            dst = os.path.join(RECYCLE, "录制_" + os.path.basename(os.path.dirname(dirpath)) + "_" + os.path.basename(dirpath))
            try:
                shutil.move(dirpath, dst)
                moved.append((dirpath, dst))
                print("移走目录:", dirpath)
            except Exception as e:
                print("移动失败:", dirpath, e)
            break
for f in os.listdir(COND) if os.path.isdir(COND) else []:
    # 精简产物按 post_id 命名，用上面收集的 ids 匹配
    if ids and any(f.startswith(i) for i in ids):
        try:
            shutil.move(os.path.join(COND, f), os.path.join(RECYCLE, f))
            moved.append((f, os.path.join(RECYCLE, f)))
            print("移走精简产物:", f)
        except Exception as e:
            print("移动产物失败:", f, e)

# 监控配置：注释掉含该博主的地址行
cfg = r"E:\tools\DouyinLiveRecorder\config\URL_config.ini"
if os.path.exists(cfg):
    txt = open(cfg, encoding="utf-8").read()
    lines = txt.splitlines()
    out, n = [], 0
    for ln in lines:
        if KEY in ln and not ln.strip().startswith("#"):
            out.append("# 已取关删除(2026-11-07) " + ln)
            n += 1
        else:
            out.append(ln)
    if n:
        open(cfg, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(f"监控配置注释掉 {n} 行")

print("\n=== 汇总 ===")
print(f"post 记录删除 {len(ids)} 条；移动文件/目录 {len(moved)} 项")
print("回收目录:", RECYCLE, "（确认无误后可整目录删除）")
print("备份 json:", BAK)
