"""
块级并行版直播精简（V3.2）

为什么要这个版本：场次并行只有 2 路时，30 场要跑 3 小时；改成「块级并行」后
所有 700 字小块一起排队，8 路并发，30 场约 20 分钟。

- 断点续跑：已有 _精简.txt 的场次跳过
- 单块失败重试 2 次，仍失败保留原文块（绝不丢内容）
- 顺序：块按原下标排序后拼接，不会串行
用法：python condense_fast.py [并发数]
"""
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"
OUTDIR = r"E:\desktop\media\_condense"
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

_lock = threading.Lock()
_done_blocks = 0
_total_blocks = 0
_t0 = 0
_tok_in = 0
_tok_out = 0
_fails = 0


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


def work(task):
    """task = (pid, idx, text)"""
    global _done_blocks, _tok_in, _tok_out, _fails
    pid, idx, text = task
    out = None
    for attempt in range(3):
        try:
            o, u = call(text)
            if o:
                out = o
                with _lock:
                    _tok_in += u.get("prompt_tokens") or 0
                    _tok_out += u.get("completion_tokens") or 0
                break
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    if out is None:
        out = text
        with _lock:
            _fails += 1
    with _lock:
        _done_blocks += 1
        if _done_blocks % 20 == 0 or _done_blocks == _total_blocks:
            el = time.time() - _t0
            per = el / max(_done_blocks, 1)
            left = per * (_total_blocks - _done_blocks)
            print(f"  块 {_done_blocks}/{_total_blocks} | 失败 {_fails} | "
                  f"{el:.0f}s 已用，剩约 {left/60:.0f} 分钟", flush=True)
    return pid, idx, out


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    global _total_blocks, _t0
    os.makedirs(OUTDIR, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = c.execute("select id, author, date, text from posts where kind='live' "
                     "and coalesce(text,'')<>'' order by length(text) desc").fetchall()
    c.close()

    todo, skip = [], 0
    for r in rows:
        sp = os.path.join(OUTDIR, r["id"] + "_精简.txt")
        if os.path.exists(sp) and os.path.getsize(sp) > 200:
            skip += 1
            continue
        chunks = split_chunks(r["text"] or "")
        todo.append({"row": r, "chunks": chunks, "parts": {}})
    total_blocks = sum(len(t["chunks"]) for t in todo)
    _total_blocks = total_blocks
    _t0 = time.time()
    print(f"场次 {len(todo)}（跳过已完成 {skip}）｜块 {total_blocks}｜并发 {workers}")
    print(f"预估：{total_blocks * 15 / workers / 60:.0f} 分钟（按每块 15 秒估）", flush=True)

    meta = {t["row"]["id"]: t for t in todo}
    tasks = []
    for t in todo:
        for i, ch in enumerate(t["chunks"]):
            tasks.append((t["row"]["id"], i, ch))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, tk) for tk in tasks]
        for f in as_completed(futs):
            pid, idx, out = f.result()
            meta[pid]["parts"][idx] = out

    # 逐场拼接落盘
    recs = []
    for pid, t in meta.items():
        parts = [t["parts"].get(i, t["chunks"][i]) for i in range(len(t["chunks"]))]
        slim = "\n".join(parts)
        text = t["row"]["text"] or ""
        with open(os.path.join(OUTDIR, pid + "_原文.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        with open(os.path.join(OUTDIR, pid + "_精简.txt"), "w", encoding="utf-8") as f:
            f.write(slim)
        rec = {"id": pid, "author": t["row"]["author"], "date": t["row"]["date"],
               "chars_in": len(text), "chars_out": len(slim),
               "ratio": round(len(slim) / max(len(text), 1), 3), "chunks": len(t["chunks"])}
        recs.append(rec)
        print(f"  ✓ {pid} {t['row']['author'][:14]} {len(text)}→{len(slim)} ({rec['ratio']:.0%})", flush=True)

    with open(os.path.join(OUTDIR, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)

    cin = sum(r["chars_in"] for r in recs)
    cout = sum(r["chars_out"] for r in recs)
    print(f"\n完成 {len(recs)} 场｜字数 {cin:,} → {cout:,}（{cout/max(cin,1):.0%}）")
    print(f"token 输入 {_tok_in:,} / 输出 {_tok_out:,}｜失败块 {_fails}｜总耗时 {(time.time()-_t0)/60:.1f} 分钟")


if __name__ == "__main__":
    main()
