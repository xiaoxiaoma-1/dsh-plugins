"""对"一般"580 本做筛选（新判据：能不能当写稿素材）

- 按字数分层自动归类
- 2000-2万字的用模型重判（新判据）
- 全库找出小说/虚构类
输出：_mid_filter.json + 打印汇总
"""
import json
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
AUDIT = r"E:\desktop\media\_book_audit_sample.json"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

SYS = "你是中文内容编辑，判断一本书对写稿有没有用。只输出 JSON。"
PROMPT = """书名：{title}
正文（节选，约 2400 字）：
{text}

判断：这本书的内容，写自媒体文章时能不能当**素材**用？（观点、故事、案例、数据、人物、历史、方法都算能用；空泛套话、纯水、小说故事不算）

只能选一个：
- "留"：有实质内容，能摘出观点/案例/故事/数据
- "删"：空泛套话、纯水、言情/玄幻/纯虚构故事、目录残页

输出 JSON：{{"verdict":"留|删","kind":"观点|方法|案例|历史|人物|小说虚构|空泛","why":"20字内"}}"""


def call(title, text, tries=3):
    body = json.dumps({"model": MODEL, "temperature": 0.2, "max_tokens": 200,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(title=title, text=text)}]}).encode()
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
            if o.get("verdict") in ("留", "删"):
                return o
        except Exception:
            time.sleep(1 + i)
    return None


def main():
    rows = json.load(open(AUDIT, encoding="utf-8"))
    mid = [x for x in rows if x["useful"] == "一般"]
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    info = {}
    for x in mid:
        r = c.execute("select count(*),sum(chars) from book_chunks where book_id=?", (x["id"],)).fetchone()
        info[x["id"]] = (r[0] or 0, r[1] or 0)

    small = [x for x in mid if info[x["id"]][1] < 2000]
    big = [x for x in mid if info[x["id"]][1] >= 20000]
    need = [x for x in mid if 2000 <= info[x["id"]][1] < 20000]
    print(f"一般共 {len(mid)}｜<2000字 {len(small)}（归删）｜>2万字 {len(big)}（归留）｜中间 {len(need)}（重判）")

    # 全库小说
    novel_ids = [x["id"] for x in rows if x.get("kind") == "小说虚构"]
    print(f"审计里判为小说虚构的：{len(novel_ids)} 本")

    jobs = []
    for x in need:
        chs = [r["content"] or "" for r in c.execute(
            "select content from book_chunks where book_id=? order by id limit 4", (x["id"],))]
        jobs.append((x, "\n…\n".join(t[:600] for t in chs)[:2400]))

    results = {}
    def work(job):
        x, text = job
        return x["id"], call(x["title_old"], text)
    with ThreadPoolExecutor(max_workers=15) as ex:
        for bid, o in ex.map(work, jobs):
            results[bid] = o or {"verdict": "留", "kind": "未知", "why": "解析失败(保守保留)"}

    keep = [x["id"] for x in big] + [x["id"] for x in need if results[x["id"]]["verdict"] == "留"]
    drop_mid = [x["id"] for x in need if results[x["id"]]["verdict"] == "删"]
    drop = [x["id"] for x in small] + drop_mid + novel_ids
    drop = list(dict.fromkeys(drop))

    out = {"keep": keep, "drop": drop,
           "detail": {x["id"]: {"title": x["title_old"], "title_new": x["title_new"],
                                "chars": info[x["id"]][1], "kind": results.get(x["id"], {}).get("kind", x["kind"]),
                                "why": results.get(x["id"], {}).get("why", x["why"])} for x in mid}}
    json.dump(out, open(r"E:\desktop\media\_mid_filter.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    c.close()

    from collections import Counter
    print(f"\n结果：保留 {len(keep)}｜删除 {len(drop)}（其中中间段重判删 {len(drop_mid)}）")
    print("重判删的类型:", Counter(results[x["id"]]["kind"] for x in need if results[x["id"]]["verdict"] == "删").most_common())
    print("\n重判样本：")
    for x in need[:10]:
        o = results[x["id"]]
        print(f"  《{x['title_old'][:20]}》 {info[x['id']][1]}字 → {o['verdict']} [{o['kind']}] {o['why']}")


if __name__ == "__main__":
    main()
