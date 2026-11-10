# -*- coding: utf-8 -*-
"""给已入库的课程逐字稿打八大板块分类（与现有 post_labels / post_classify 体系同源）"""
import json, sqlite3, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, r"E:\desktop\media")
sys.stdout.reconfigure(encoding="utf-8")
from classify3 import TREE, ALL_SUBS, TREE_TXT  # noqa

DB = r"E:\desktop\media\workbench.db"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

SYS = "你是中文内容分类与索引专家。只能从给定子类清单里选，绝不造子类；主题标签可以自由生成但必须具体。只输出 JSON。"
PROMPT = """内容来源：{title}
正文：
{text}

【大类→子类清单】（子类只能从这里选，共 {total} 个）
{tree}

【任务】
1. topics：这段内容属于哪几个大类？可多选，1-3 个，按重要度排序。
2. subs：具体能挂哪些子类？1-4 个，必须来自上面清单，可跨大类。
3. tags：这段内容具体讲了什么？3-6 个中文主题词，每个 2-8 字，不许用"人生""成长""思维"这类空词。

只输出 JSON：
{{"topics":["大类1"],"subs":["子类1","子类2"],"tags":["标签1","标签2","标签3"],"why":"不超过20字"}}"""

_lock = threading.RLock()
res = {}
fail = 0


def call(title, text, tries=3):
    body = json.dumps({"model": MODEL, "temperature": 0.15, "max_tokens": 400,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(
                                        title=title, text=text[:2600], total=len(ALL_SUBS), tree=TREE_TXT)}]}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.load(r)
            s = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            s = s[s.find("{"): s.rfind("}") + 1]
            o = json.loads(s)
            topics = [x for x in (o.get("topics") or []) if x in TREE][:3]
            subs = [x for x in (o.get("subs") or []) if x in ALL_SUBS][:4]
            tags = []
            for t in (o.get("tags") or []):
                t = str(t).strip()
                if 2 <= len(t) <= 8 and t not in tags:
                    tags.append(t)
            if not topics:
                raise ValueError("空")
            return {"topics": topics, "subs": subs, "tags": tags[:6], "why": str(o.get("why") or "")[:30]}
        except Exception as e:
            time.sleep(1 + i)
    return {"topics": [], "subs": [], "tags": [], "why": "失败"}


def work(row):
    global fail
    pid, title, text = row
    o = call(title, text)
    with _lock:
        if not o["topics"]:
            fail += 1
        res[pid] = o
    return pid


def main():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = []
    for r in c.execute("select p.id, coalesce(s.title,'') t, coalesce(p.text,'') txt "
                       "from posts p left join post_sources s on s.post_id=p.id "
                       "where p.kind='课程' and length(coalesce(p.text,''))>150"):
        rows.append((r["id"], r["t"], r["txt"]))
    c.close()
    print("待分类课程稿 %d 篇" % len(rows), flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(work, rows))
    print("分类完成 %.1fs 失败 %d" % (time.time() - t0, fail), flush=True)

    json.dump(res, open(r"E:\desktop\media\_xet_classify.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    c = sqlite3.connect(DB)
    c.execute("""create table if not exists post_classify(
        src_id text primary key, topics text, subs text, tags text, why text, created_at text)""")
    c.execute("""create table if not exists post_labels(
        post_id text primary key, topic text, topic2 text, sub text, subs text,
        conf real, created_at text)""")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    for pid, o in res.items():
        if not o["topics"]:
            continue
        c.execute("insert or replace into post_classify values(?,?,?,?,?,?)",
                  ("post:" + pid, ",".join(o["topics"]), ",".join(o["subs"]),
                   ",".join(o["tags"]), o["why"], now))
        c.execute("insert or replace into post_labels(post_id,topic,topic2,sub,subs,conf,created_at)"
                  " values(?,?,?,?,?,?,?)",
                  (pid, o["topics"][0], (o["topics"][1] if len(o["topics"]) > 1 else ""),
                   (o["subs"][0] if o["subs"] else ""), ",".join(o["subs"]), 0.9, now))
        c.execute("update posts set topic_override=? where id=?", (o["topics"][0], pid))
    c.commit()

    print("\n结果：")
    for r in c.execute("select s.title, l.topic, l.topic2, l.sub, l.subs from post_labels l "
                       "join posts p on p.id=l.post_id left join post_sources s on s.post_id=p.id "
                       "where p.kind='课程' order by s.title"):
        print("  %-34s %-10s %-10s %-12s %s" % ((r[0] or '')[:32], r[1], r[2] or '-', r[3], r[4]))
    print("\n板块分布:", c.execute(
        "select topic,count(*) from post_labels l join posts p on p.id=l.post_id "
        "where p.kind='课程' group by topic order by 2 desc").fetchall())
    print("post_labels 总数:", c.execute("select count(*) from post_labels").fetchone()[0])
    print("post_classify 总数:", c.execute("select count(*) from post_classify").fetchone()[0])
    c.close()


if __name__ == "__main__":
    main()
