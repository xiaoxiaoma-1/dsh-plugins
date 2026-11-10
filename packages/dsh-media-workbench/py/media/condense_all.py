"""
批量精简：30 场直播逐字稿 → 精简稿（V3.2，逐块改写，不丢观点）

- 已精简过的场次跳过（断点续跑）
- 产物：E:\desktop\media\_condense\<post_id>_精简.txt / _原文.txt
- 汇总：E:\desktop\media\_condense\_summary.json
用法：python condense_all.py [并行场次]
"""
import json
import os
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"
OUTDIR = r"E:\desktop\media\_condense"
SUMMARY = os.path.join(OUTDIR, "_summary.json")
BASE = "http://127.0.0.1:8326/v1"
KEY_FILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
CHUNK = 700

SYS = "你是中文文字编辑。任务只有一件：把口语转写精炼成通顺的书面文字。绝不总结、绝不添加内容。"

PROMPT = """下面是一段直播口语转写，请精炼改写。

【怎么删】
- 删掉口头禅、语气词（啊、对吧、就是说、那个、然后然后）、重复的句子和词
- 删掉无信息的寒暄、跑题闲聊、与主题无关的插话
- 删掉主播自问自答式的废话（"这么说大家能理解吧"这类）
- 同一件事反复说了好几遍的，只保留说得最清楚的那一次

【怎么改】
- 口语改通顺书面语，顺着原来的叙述顺序，不要重排
- 保留第一人称和原来的讲话口径

【绝对不许】
- 不许漏掉任何观点、方法、案例、数字、人名
- 不许添加原文没有的内容、不许补充你自己的解释
- 不许总结成要点、不许分条、不许加标题
- 不许改变原意

直接输出精炼后的正文，不要任何说明。

原文：
{text}"""


def call(text, max_tokens=1500, timeout=180):
    key = open(KEY_FILE, encoding="utf-8").read().strip()
    body = json.dumps({
        "model": MODEL, "temperature": 0.3, "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": PROMPT.format(text=text)}],
    }).encode("utf-8")
    req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.load(r)
    c = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return c.strip(), (j.get("usage") or {})


def split_chunks(text, size=CHUNK):
    out, buf = [], ""
    for ch in text:
        buf += ch
        if len(buf) >= size:
            cut = -1
            for mark in ("。", "！", "？", "\n", "，", ",", " "):
                k = buf.rfind(mark, max(0, len(buf) - 120))
                if k > cut:
                    cut = k
            if cut > size * 0.5:
                out.append(buf[:cut + 1]); buf = buf[cut + 1:]
            else:
                out.append(buf); buf = ""
    if buf.strip():
        out.append(buf)
    return [c for c in out if c.strip()]


def do_one(row):
    pid = row["id"]
    slim_path = os.path.join(OUTDIR, pid + "_精简.txt")
    if os.path.exists(slim_path) and os.path.getsize(slim_path) > 200:
        return {"id": pid, "skip": True}
    text = row["text"] or ""
    chunks = split_chunks(text)
    outs, tin, tout, fails = [], 0, 0, 0
    t0 = time.time()
    for ch in chunks:
        try:
            o, u = call(ch)
            if not o:
                raise RuntimeError("空返回")
            outs.append(o)
            tin += u.get("prompt_tokens") or 0
            tout += u.get("completion_tokens") or 0
        except Exception:
            fails += 1
            outs.append(ch)  # 失败保留原文，不丢内容
        time.sleep(0.1)
    slim = "\n".join(outs)
    with open(os.path.join(OUTDIR, pid + "_原文.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(slim_path, "w", encoding="utf-8") as f:
        f.write(slim)
    rec = {"id": pid, "author": row["author"], "date": row["date"], "chars_in": len(text),
           "chars_out": len(slim), "ratio": round(len(slim) / max(len(text), 1), 3),
           "chunks": len(chunks), "fails": fails, "tok_in": tin, "tok_out": tout,
           "sec": round(time.time() - t0), "skip": False}
    print(f"  ✓ {pid} {row['author'][:14]} {len(text)}→{len(slim)} ({rec['ratio']:.0%}) "
          f"{rec['sec']}s fail={fails}", flush=True)
    return rec


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    os.makedirs(OUTDIR, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = c.execute("select id, author, date, text from posts where kind='live' "
                     "and coalesce(text,'')<>'' order by length(text) desc").fetchall()
    c.close()
    print(f"共 {len(rows)} 场，并行 {workers}")
    t0 = time.time()
    recs = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(do_one, rows):
            recs.append(r)
            done = len([x for x in recs if not x.get("skip")])
            print(f"[{len(recs)}/{len(rows)}] 已完成 {done} 场，累计 {time.time()-t0:.0f}s", flush=True)
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)
    ok = [x for x in recs if not x.get("skip")]
    tin = sum(x.get("tok_in", 0) for x in ok)
    tout = sum(x.get("tok_out", 0) for x in ok)
    cin = sum(x.get("chars_in", 0) for x in ok)
    cout = sum(x.get("chars_out", 0) for x in ok)
    print(f"\n完成 {len(ok)} 场（跳过 {len(recs)-len(ok)}）")
    print(f"字数 {cin:,} → {cout:,}（{cout/max(cin,1):.0%}）")
    print(f"token 输入 {tin:,} / 输出 {tout:,}；总耗时 {(time.time()-t0)/60:.0f} 分钟")


if __name__ == "__main__":
    main()
