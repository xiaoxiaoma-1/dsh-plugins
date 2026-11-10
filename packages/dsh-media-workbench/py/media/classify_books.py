"""书库全量分类（2166 本 → 8 大类 + 33 子类），写 book_labels 表

每本取：标题 + 作者 + 开头/中段/后段各约 800 字，共约 2400 字。
一本允许多个大类（最多 2），子类 1-3 个。
用法：python classify_books.py [并发]
"""
import json
import sqlite3
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

TREE = {
    "权谋与政治": ["权力与博弈", "人情世故", "体制与生存", "毛选"],
    "商业与变现": ["搞钱路径", "定价与成交", "流量获客", "团队与合伙"],
    "内容创作": ["选题", "标题与开头", "结构与节奏", "平台规则", "起号与增长"],
    "心理与人性": ["自我认知", "情绪", "关系", "欲望与动机"],
    "语言与思维": ["表达与说服", "逻辑", "认知模型", "反常识"],
    "AI 与工具": ["AI 用法", "提示词", "自动化", "效率工具"],
    "国学与哲学": ["心学", "道家与易", "人生选择", "历史人物"],
    "身心与生活": ["身体", "冥想", "阅读", "生活方式"],
}
ALL = {s for v in TREE.values() for s in v}
TREE_TXT = "\n".join(f"{d}：{' / '.join(v)}" for d, v in TREE.items())
SYS = "你是中文书籍分类器。只能从给定清单里选，绝不造词。只输出 JSON。"
PROMPT = """书名：{title}
作者：{author}
正文节选：
{text}

【大类】{doms}
【大类→子类】
{tree}

这本书主要在讲什么？输出 JSON：
{{"d":"主要大类","d2":"次要大类或 null","subs":["子类1","子类2"],"conf":0.0-1.0}}
要求：d 必填；一本书可跨两个大类（d2）；subs 1-3 个，必须属于 d 或 d2。"""

_lock = threading.Lock()
_n = 0
_tot = 0
_t0 = 0
_fail = 0


def call(title, author, text, tries=3):
    body = json.dumps({"model": MODEL, "temperature": 0.2, "max_tokens": 360,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(
                                        title=title, author=author or "未知", text=text,
                                        doms=" / ".join(TREE.keys()), tree=TREE_TXT)}]}).encode()
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
            d, d2 = o.get("d"), o.get("d2")
            if d not in TREE:
                d = None
            if d2 not in TREE:
                d2 = None
            subs = [x for x in (o.get("subs") or [])
                    if x in ALL and (x in TREE.get(d or "", []) or x in TREE.get(d2 or "", []))]
            return {"d": d, "d2": d2, "subs": subs[:3], "conf": float(o.get("conf") or 0.5)}
        except Exception:
            time.sleep(1 + i)
    return {"d": None, "d2": None, "subs": [], "conf": 0.0}


def work(row):
    global _n, _fail
    o = call(row["title"], row["author"], row["excerpt"] or "")
    with _lock:
        _n += 1
        if not o["d"]:
            _fail += 1
        if _n % 100 == 0:
            el = time.time() - _t0
            print(f"  {_n}/{_tot} | {el/60:.1f} 分钟 | 剩约 {el/_n*(_tot-_n)/60:.0f} 分钟 | 失败 {_fail}", flush=True)
    return row["id"], o


def main():
    global _tot, _t0
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    books = c.execute("select id,title,coalesce(author,'') a,coalesce(pages,0) p from books").fetchall()
    # 取每本 3 段节选
    rows = []
    for b in books:
        chs = c.execute("select content from book_chunks where book_id=? order by id", (b["id"],)).fetchall()
        if not chs:
            continue
        texts = [x["content"] or "" for x in chs]
        n = len(texts)
        picks = [texts[0], texts[n // 2] if n > 2 else "", texts[min(n - 1, n * 2 // 3)]]
        excerpt = "\n…\n".join(t[:800] for t in picks if t)
        rows.append({"id": b["id"], "title": b["title"], "author": b["a"], "excerpt": excerpt[:2600]})
    c.close()
    _tot = len(rows); _t0 = time.time()
    print(f"待分类 {_tot} 本（无正文的跳过）｜并发 {workers}", flush=True)

    res = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for bid, o in ex.map(work, rows):
            res[bid] = o

    with open(r"E:\desktop\media\_book_labels.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    c = sqlite3.connect(DB)
    c.execute("""create table if not exists book_labels(
        book_id text primary key, topic text, topic2 text, sub text, subs text,
        conf real, created_at text)""")
    c.execute("delete from book_labels")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    for bid, o in res.items():
        c.execute("insert into book_labels(book_id,topic,topic2,sub,subs,conf,created_at)"
                  " values(?,?,?,?,?,?,?)",
                  (bid, o["d"] or "", o["d2"] or "", (o["subs"][0] if o["subs"] else ""),
                   ",".join(o["subs"]), o["conf"], now))
    c.commit(); c.close()

    from collections import Counter
    print(f"\n完成 {len(res)} 本｜无标签 {_fail}｜耗时 {(time.time()-_t0)/60:.1f} 分钟")
    print("大类分布:", Counter(o["d"] for o in res.values()).most_common())


if __name__ == "__main__":
    main()
