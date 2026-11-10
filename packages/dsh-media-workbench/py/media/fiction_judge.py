# -*- coding: utf-8 -*-
"""全库虚构/非虚构判定（找残余小说）—— 二分类，用"先摘特征再判断"压塌缩"""
import json, os, sqlite3, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
OUT = r"E:\desktop\media\_fiction.json"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

SYS = "你是中文图书类型鉴定员。先摘特征再下结论，只输出 JSON。"
PROMPT = """书名：{title}
作者：{author}
正文节选：
{text}

【第一步：摘两个特征】
- 情节证据：节选里有没有「人物对话、场景描写、连续的情节推进」？摘一句原文（≤25字），没有填 null
- 知识证据：节选里有没有「方法步骤、数据、论证、真实史料」？摘一句原文（≤25字），没有填 null

【第二步：判断类型】
type 只能取：小说｜传记｜历史纪实｜教材教程｜商业/投资实务｜心理自助｜哲思随笔｜其他非虚构
- 小说 = 虚构人物与情节推动的书（含玄幻、言情、历史小说、网文）
- 传记 = 真实人物的生平
- 情节证据强、知识证据几乎没有 → 小说
- 知识证据强 → 非虚构
- 两者都有 → 看主体，传记按传记算

只输出 JSON：
{{"s1":"原文或null","s2":"原文或null","type":"上面之一","fiction":true|false,"why":"不超过15字"}}"""

_lock = threading.RLock()
_n = _tot = _fail = 0
_t0 = 0.0
res = {}


def call(title, author, text, tries=3):
    body = json.dumps({"model": MODEL, "temperature": 0.1, "max_tokens": 260,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(
                                        title=title, author=author or "未知", text=text)}]}).encode()
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
            tp = (o.get("type") or "").strip()
            if tp not in ("小说", "传记", "历史纪实", "教材教程", "商业/投资实务",
                          "心理自助", "哲思随笔", "其他非虚构"):
                tp = ""
            return {"type": tp, "fiction": bool(o.get("fiction")),
                    "why": str(o.get("why") or "")[:30],
                    "s1": (o.get("s1") or "")[:60], "s2": (o.get("s2") or "")[:60]}
        except Exception:
            time.sleep(1 + i)
    return {"type": "", "fiction": None, "why": "失败", "s1": "", "s2": ""}


def work(row):
    global _n, _fail
    o = call(row[1], row[2], row[3])
    with _lock:
        _n += 1
        if not o["type"]:
            _fail += 1
        res[row[0]] = o
        if _n % 200 == 0 or _n == _tot:
            print("  %d/%d | %.1f 分 | 失败 %d" % (_n, _tot, (time.time() - _t0) / 60, _fail), flush=True)
            dump()
    return row[0]


def dump():
    with _lock:
        snap = dict(res)
    tmp = OUT + ".tmp"
    json.dump(snap, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)


def main():
    global _tot, _t0
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 48
    c = sqlite3.connect(DB)
    rows = []
    for bid, t, a in c.execute("select id, title, coalesce(author,'') from books").fetchall():
        if os.path.exists(OUT):
            pass
        chs = c.execute("select content from book_chunks where book_id=? order by page_from limit 6",
                        (bid,)).fetchall()
        txt = "\n…\n".join((x[0] or "")[:500] for x in chs)
        rows.append((bid, t, a, txt[:2200]))
    c.close()
    _tot = len(rows)
    _t0 = time.time()
    print("待判 %d 本｜并发 %d" % (_tot, workers), flush=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, rows))
    dump()

    c = sqlite3.connect(DB)
    c.execute("drop table if exists book_fiction")
    c.execute("create table book_fiction(book_id text primary key, type text, fiction int, why text)")
    for bid, o in res.items():
        c.execute("insert or replace into book_fiction values(?,?,?,?)",
                  (bid, o.get("type"), 1 if o.get("fiction") else 0, o.get("why")))
    c.commit()
    c.close()

    from collections import Counter
    ok = [o for o in res.values() if o.get("type")]
    print("\n完成 %d｜失败 %d｜%.1f 分" % (len(res), _fail, (time.time() - _t0) / 60))
    print("类型分布:", Counter(o["type"] for o in ok).most_common())
    print("小说数:", sum(1 for o in ok if o["fiction"]))


if __name__ == "__main__":
    main()
