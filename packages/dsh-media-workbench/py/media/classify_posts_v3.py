# -*- coding: utf-8 -*-
"""把抖音文案 posts + 直播分段 live_segments 纳入同一套新分类体系（72 子类 + 三级标签）"""
import json, os, sqlite3, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, r"E:\desktop\media")
from classify3 import TREE, ALL_SUBS, TREE_TXT  # noqa

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
OUT = r"E:\desktop\media\_post_classify.json"
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
1. topics：这段内容属于哪几个大类？可多选，1-3 个。
2. subs：具体能挂哪些子类？**1-4 个**，必须来自上面清单，可跨大类。
3. tags：这段内容**具体讲了什么**？3-6 个中文主题词，每个 2-8 字，不许用"人生""成长""思维"这类空词。

只输出 JSON：
{{"topics":["大类1"],"subs":["子类1","子类2"],"tags":["标签1","标签2","标签3"],"why":"不超过20字"}}"""

_lock = threading.RLock()
done = total = fail = 0
t0 = time.time()
res = {}


def call(title, text, tries=3):
    body = json.dumps({"model": MODEL, "temperature": 0.15, "max_tokens": 380,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(
                                        title=title, text=text[:2000], total=len(ALL_SUBS),
                                        tree=TREE_TXT)}]}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=90) as r:
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
            return {"topics": topics, "subs": subs, "tags": tags[:6],
                    "why": str(o.get("why") or "")[:30]}
        except Exception:
            time.sleep(1 + i)
    return {"topics": [], "subs": [], "tags": [], "why": "失败"}


def work(row):
    global done, fail
    key, title, text = row
    o = call(title, text)
    with _lock:
        done += 1
        if not o["topics"]:
            fail += 1
        res[key] = o
        if done % 200 == 0 or done == total:
            print("  %d/%d | %.1f 分 | 失败 %d" % (done, total, (time.time() - t0) / 60, fail), flush=True)
            dump()
    return 1


def dump():
    with _lock:
        snap = dict(res)
    tmp = OUT + ".tmp"
    json.dump(snap, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)


def main():
    global total, t0
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 48
    c = sqlite3.connect(DB)
    rows = []
    for pid, author, text in c.execute(
            "select id, coalesce(author,''), coalesce(text,'') from posts where length(coalesce(text,''))>150"):
        rows.append(("post:" + str(pid), (author or "抖音文案")[:20], text))
    for sid, author, text in c.execute(
            "select id, coalesce(author,''), coalesce(text,'') from live_segments where length(coalesce(text,''))>150"):
        rows.append(("live:" + str(sid), (author or "")[:16] + "·直播", text))
    c.close()
    total = len(rows)
    t0 = time.time()
    print("待分类：抖音文案+直播 %d 条｜并发 %d" % (total, workers), flush=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, rows))
    dump()

    c = sqlite3.connect(DB)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""create table if not exists post_classify(
        src_id text primary key, topics text, subs text, tags text, why text, created_at text)""")
    c.execute("delete from post_classify")
    for k, o in res.items():
        if not o["topics"]:
            continue
        c.execute("insert or replace into post_classify values(?,?,?,?,?,?)",
                  (k, ",".join(o["topics"]), ",".join(o["subs"]), ",".join(o["tags"]), o["why"], now))
    c.commit()
    c.close()

    from collections import Counter
    ok = [o for o in res.values() if o["topics"]]
    print("\n完成 %d｜失败 %d｜%.1f 分" % (len(res), fail, (time.time() - t0) / 60))
    print("大类分布:", Counter(x for o in ok for x in o["topics"]).most_common())
    print("子类覆盖:", len({s for o in ok for s in o["subs"]}), "/", len(ALL_SUBS))
    print("平均标签 %.1f 个" % (sum(len(o["tags"]) for o in ok) / max(1, len(ok))))


if __name__ == "__main__":
    main()
