"""增量收尾：删空壳书 + 给有正文但没分类的书补分类

用法：python finish_books.py
"""
import json
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
STAMP = time.strftime("%Y%m%d_%H%M%S")

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
SYS = "你是中文书籍分类器。只输出 JSON。"
PROMPT = """书名：{title}
正文节选：
{text}

【大类】{doms}
【大类→子类】
{tree}

输出 JSON：{{"d":"大类","d2":null,"subs":["子类1"],"conf":0.0-1.0}}"""


def call(title, text, tries=3):
    body = json.dumps({"model": MODEL, "temperature": 0.2, "max_tokens": 300,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(
                                        title=title, text=text, doms=" / ".join(TREE.keys()),
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


def main():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    cur = c.cursor()

    # 1) 删空壳（没有正文）
    empties = cur.execute("""select b.id,b.title from books b
        where (select count(*) from book_chunks ch where ch.book_id=b.id)=0""").fetchall()
    print(f"空壳书（无正文）：{len(empties)} 本 → 删")
    if empties:
        bak = [{"id": x["id"], "title": x["title"]} for x in empties]
        json.dump(bak, open(rf"E:\desktop\media\_deleted_empty_books_{STAMP}.json", "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
        ids = [x["id"] for x in empties]
        q = ",".join("?" * len(ids))
        for t in ("book_chunks", "book_topics", "book_labels"):
            try:
                cur.execute(f"delete from {t} where book_id in ({q})", ids)
            except Exception:
                pass
        n = cur.execute(f"delete from books where id in ({q})", ids).rowcount
        c.commit()
        print(f"已删空壳 {n} 本（备份 _deleted_empty_books_{STAMP}.json）")

    # 2) 增量分类：有正文但没 labels
    todo = cur.execute("""select b.id,b.title,coalesce(b.author,'') a from books b
        left join book_labels l on l.book_id=b.id
        where l.book_id is null
          and (select count(*) from book_chunks ch where ch.book_id=b.id)>0""").fetchall()
    print(f"\n待补分类（有正文）：{len(todo)} 本")

    # 先在主线程把正文取出来（sqlite 的 cursor 不能跨线程）
    prefetch = {}
    for b in todo:
        chs = [r["content"] or "" for r in cur.execute(
            "select content from book_chunks where book_id=? order by id limit 4", (b["id"],))]
        prefetch[b["id"]] = "\n…\n".join(t[:700] for t in chs)[:2800]

    def work(b):
        return b["id"], call(b["title"], prefetch[b["id"]])

    res = {}
    if todo:
        with ThreadPoolExecutor(max_workers=12) as ex:
            for bid, o in ex.map(work, todo):
                res[bid] = o
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        for bid, o in res.items():
            cur.execute("insert or replace into book_labels(book_id,topic,topic2,sub,subs,conf,created_at)"
                        " values(?,?,?,?,?,?,?)",
                        (bid, o["d"] or "", o["d2"] or "", (o["subs"][0] if o["subs"] else ""),
                         ",".join(o["subs"]), o["conf"], now))
        c.commit()

    total = cur.execute("select count(*) from books").fetchone()[0]
    labeled = cur.execute("select count(*) from book_labels").fetchone()[0]
    empty_left = cur.execute("""select count(*) from books b where
        (select count(*) from book_chunks ch where ch.book_id=b.id)=0""").fetchone()[0]
    print(f"\n完成：书 {total} 本｜已分类 {labeled}｜无正文 {empty_left}")
    print("补分类结果:", {k: (v["d"] or "未分") for k, v in list(res.items())[:8]})
    c.close()


if __name__ == "__main__":
    main()
