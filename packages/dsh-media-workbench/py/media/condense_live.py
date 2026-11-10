"""
直播逐字稿「精简改写」样板（V3.2）

原则：只删废话、改口语为书面，不丢观点、不加内容、不改原意。
原文保留，精简稿另存。
用法：python condense_live.py [post_id] [最大字数]
产物：E:\\desktop\\media\\_condense\\<post_id>_原文.txt / _精简.txt / _对照.md
"""
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"
OUTDIR = r"E:\desktop\media\_condense"
BASE = "http://127.0.0.1:8326/v1"
KEY_FILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
CHUNK = 700  # 每块原文字数（转写无标点，块必须小，否则输出超 max_tokens）

SYS = "你是中文文字编辑。任务只有一件：把口语转写精炼成通顺的书面文字。绝不总结、绝不提炼要点、绝不添加内容。"

PROMPT = """下面是一段直播口语转写，请精炼改写。

【怎么删】
- 删掉口头禅、语气词（啊、对吧、就是说、那个、然后然后）、重复的句子和词
- 删掉无信息的寒暄、跟内容无关的跑题闲聊、与主题无关的插话
- 删掉主播自问自答式的废话（"这么说大家能理解吧"这类）

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


def call(text, max_tokens=1400, timeout=150):
    key = open(KEY_FILE, encoding="utf-8").read().strip()
    body = json.dumps({
        "model": MODEL, "temperature": 0.3, "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": PROMPT.format(text=text)},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.load(r)
    c = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return c.strip(), (j.get("usage") or {})


def split_sents(text, size):
    """按标点优先切块；转写里常常整段只有逗号，所以退化为找最近的逗号/空格硬切，绝不切出超长块"""
    out, buf = [], ""
    for ch in text:
        buf += ch
        if len(buf) >= size:
            # 在最后 120 字里找一个像样的断点
            cut = -1
            for mark in ("。", "！", "？", "\n", "，", ",", " "):
                k = buf.rfind(mark, max(0, len(buf) - 120))
                if k > cut:
                    cut = k
            if cut > size * 0.5:
                out.append(buf[:cut + 1])
                buf = buf[cut + 1:]
            else:
                out.append(buf)
                buf = ""
    if buf.strip():
        out.append(buf)
    return [c for c in out if c.strip()]


def main():
    pid = sys.argv[1] if len(sys.argv) > 1 else None
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 16000
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    cur = c.cursor()
    if not pid:
        # 取字数最接近 15000 的一场
        row = cur.execute(
            "select id, author, date, text, length(text) n from posts where kind='live' "
            "order by abs(length(text)-15000) limit 1").fetchone()
    else:
        row = cur.execute("select id, author, date, text, length(text) n from posts where id=?", (pid,)).fetchone()
    c.close()
    if not row:
        print("没找到这场直播")
        return
    text = (row["text"] or "")[:cap]
    print(f"场次：{row['id']} | {row['author']} | {row['date']} | 原文字数 {row['n']}（本次处理 {len(text)}）")
    chunks = split_sents(text, CHUNK)
    print(f"切 {len(chunks)} 块")

    os.makedirs(OUTDIR, exist_ok=True)
    outs, tin, tout, t0 = [], 0, 0, time.time()
    for i, ch in enumerate(chunks, 1):
        try:
            o, usage = call(ch)
            tin += usage.get("prompt_tokens") or 0
            tout += usage.get("completion_tokens") or 0
            outs.append(o)
            print(f"  [{i}/{len(chunks)}] {len(ch)} -> {len(o)} 字 ({len(o)/max(len(ch),1):.0%})", flush=True)
        except Exception as e:
            print(f"  [{i}/{len(chunks)}] 失败：{str(e)[:80]}", flush=True)
            outs.append(ch)  # 失败就保留原文，不丢内容
        time.sleep(0.2)

    slim = "\n".join(outs)
    base = os.path.join(OUTDIR, row["id"])
    with open(base + "_原文.txt", "w", encoding="utf-8") as f:
        f.write(text)
    with open(base + "_精简.txt", "w", encoding="utf-8") as f:
        f.write(slim)
    with open(base + "_对照.md", "w", encoding="utf-8") as f:
        f.write(f"# {row['author']} {row['date']} 直播精简对照\n\n")
        f.write(f"- 原文 {len(text)} 字 → 精简 {len(slim)} 字（{len(slim)/max(len(text),1):.0%}）\n")
        f.write(f"- 用时 {time.time()-t0:.0f}s，token 输入 {tin:,} / 输出 {tout:,}\n\n")
        f.write("## 精简稿（前 1200 字）\n\n" + slim[:1200] + "\n\n---\n\n")
        f.write("## 原文（前 1200 字）\n\n" + text[:1200] + "\n")

    print(f"\n原文 {len(text)} 字 → 精简 {len(slim)} 字（{len(slim)/max(len(text),1):.0%}）")
    print(f"token：输入 {tin:,} / 输出 {tout:,}；用时 {time.time()-t0:.0f}s")
    print("产物：", base + "_对照.md")


if __name__ == "__main__":
    main()
