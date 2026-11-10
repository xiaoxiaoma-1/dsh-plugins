"""书库审计：读正文 → 重拟书名 + 判断有没有用（先跑小样）

输出字段：title_new（重拟书名）/ kind（内容类型）/ useful（干货/一般/垃圾）/ why（理由）
用法：python book_audit.py [本数] [并发]
产物：E:\\desktop\\media\\_book_audit_sample.json
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

SYS = "你是中文编辑，负责给书重新起名并判断它值不值得留。只输出 JSON，不要解释。"
PROMPT = """现有书名：{title}
作者：{author}
正文节选（可能有多处）：
{text}

请做三件事：
1. 给这本书**重新起一个中文书名**，12-20 字，要让人一看就知道里面讲什么（保留原来的核心概念，不要空泛，不要加书名号）
2. 判断内容类型 kind，从这些里选一个：观点/方法论/课程讲义/工具手册/案例集/小说虚构/目录残页/其他
3. 判断值得留吗 useful，从这些里选一个：
   - "干货"：有具体方法、步骤、案例、可直接用的知识
   - "一般"：有点内容但空泛、重复、价值有限
   - "垃圾"：目录页/版权页/乱码残页/无正文/纯虚构故事，没有可用的知识

输出 JSON：
{{"title_new":"…","kind":"…","useful":"干货|一般|垃圾","why":"20字内理由"}}

注意：书名可能是乱码或代号（如《65》《ln03 …》），不要被书名骗，**以正文内容为准**。"""


def call(title, author, text, tries=3):
    body = json.dumps({"model": MODEL, "temperature": 0.3, "max_tokens": 400,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(
                                        title=title, author=author or "未知", text=text)}]}).encode()
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
            if o.get("title_new") and o.get("useful") in ("干货", "一般", "垃圾"):
                return o
        except Exception:
            time.sleep(1 + i)
    return None


_lock = threading.Lock()
_n = 0
_tot = 0
_t0 = 0


def work(row):
    global _n
    o = call(row["title"], row["author"], row["excerpt"])
    with _lock:
        _n += 1
        if _n % 10 == 0:
            print(f"  {_n}/{_tot} | {time.time()-_t0:.0f}s", flush=True)
    return row, o


def main():
    global _tot, _t0
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    # 优先取：书名可疑（短/带编码）的，最能验证"重拟书名"有没有用
    books = c.execute("""select id,title,coalesce(author,'') author,coalesce(pages,0) pages
        from books order by (length(title)<=6) desc, random() limit ?""", (limit,)).fetchall()
    rows = []
    for b in books:
        chs = [x["content"] or "" for x in c.execute(
            "select content from book_chunks where book_id=? order by id", (b["id"],))]
        if not chs:
            continue
        n = len(chs)
        picks = [chs[0], chs[n // 3] if n > 3 else "", chs[n // 2] if n > 2 else "",
                 chs[min(n - 1, n * 2 // 3)]]
        excerpt = "\n…\n".join(t[:1000] for t in picks if t)
        rows.append({"id": b["id"], "title": b["title"], "author": b["author"],
                     "excerpt": excerpt[:4200]})
    c.close()
    _tot = len(rows); _t0 = time.time()
    print(f"试跑 {_tot} 本｜并发 {workers}", flush=True)

    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for row, o in ex.map(work, rows):
            out.append({"id": row["id"], "title_old": row["title"],
                        "author": row["author"], "excerpt_chars": len(row["excerpt"]),
                        **(o or {"title_new": "", "kind": "", "useful": "解析失败", "why": ""})})

    with open(r"E:\desktop\media\_book_audit_sample.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    from collections import Counter
    print(f"\n完成 {len(out)} 本｜{time.time()-_t0:.0f}s")
    print("有用性:", Counter(x["useful"] for x in out).most_common())
    print("类型:", Counter(x["kind"] for x in out).most_common())
    print("\n=== 样例（旧名 → 新名 / 判定）===")
    for x in out[:12]:
        print(f"  《{x['title_old'][:20]}》→《{x['title_new'][:24]}》 [{x['kind']}/{x['useful']}] {x['why']}")


if __name__ == "__main__":
    main()
