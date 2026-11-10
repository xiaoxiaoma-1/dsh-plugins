# -*- coding: utf-8 -*-
"""每日简报：读当天的进度行与新增记忆 + 库统计 → V3.2 生成五板块日报。

用法：python daily_report.py [YYYY-MM-DD]   默认今天
输出：E:\\desktop\\每日简报\\<日期>.md
"""
import datetime
import json
import os
import sqlite3
import sys
import urllib.request

# 计划任务改用 pythonw 跑（不弹黑框）时 sys.stdout/stderr 都是 None，print 会崩
if sys.stdout is None or sys.stderr is None:
    try:
        _null = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        _null = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = _null
    if sys.stderr is None:
        sys.stderr = _null
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MEM = r"C:\Users\Administrator\.my-memory\memory.db"
WB = r"E:\desktop\media\workbench.db"
OUT = r"E:\desktop\每日简报"
GATEWAY = "http://127.0.0.1:8326/v1/chat/completions"
KEYFILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
LEVELS = ("project", "lesson", "fact", "rules", "user", "topic", "soul")

SYS = """你在帮一个做 AI 内容的人写当天的工作日报。只输出 Markdown，不要解释。
严格按这五个二级标题，不要增删：
## 今天做了什么
## 高光时刻
## 今天用 AI 干了什么
## 卡在哪
## 数字

要求：
- 「今天做了什么」3–5 条，按项目归类，每条一句话，带关键数字。
- 「高光时刻」只留他本人说过的判断句、金句、新想法，原话照抄，标成引用。没有就写"今天没有"。
- 「今天用 AI 干了什么」写成一段 80 字以内、第一人称、可以直接发朋友圈的口吻，不用形容词堆砌，要有具体动作和数字。
- 「卡在哪」列没做完、等确认的事，每条一句话。
- 「数字」用列表，只放给定的统计数字，不要编。
- 全文不超过 600 字。不用"综上所述""值得注意的是"。"""


def key():
    return open(KEYFILE, encoding="utf-8").read().strip()


def ask(prompt, timeout=180):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
        "temperature": 0.3, "max_tokens": 1600,
    }).encode("utf-8")
    req = urllib.request.Request(GATEWAY, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    msg = j["choices"][0]["message"]
    return msg.get("content") or ""


def gather(day):
    lines = []
    c = sqlite3.connect(MEM)
    # 进度行：local_time 形如 2026-11-04 09:10 (周三) Asia/Shanghai
    for r in c.execute("select content from progress where local_time like ? order by created_at", (day + "%",)):
        lines.append("· " + r[0])
    memos = []
    for t in LEVELS:
        try:
            rows = c.execute(
                "select title, substr(content,1,300) from %s "
                "where date(created_at/1000,'unixepoch','localtime')=? " % t, (day,)).fetchall()
        except Exception:
            continue
        for title, content in rows:
            memos.append("[%s] %s：%s" % (t, title, content.replace("\n", " ")[:200]))
    c.close()

    # 库统计
    stats = {}
    try:
        w = sqlite3.connect(WB)
        stats["素材总数"] = w.execute("select count(*) from split_items").fetchone()[0]
        stats["书源素材"] = w.execute("select count(*) from split_items where source='book'").fetchone()[0]
        stats["今日新增素材"] = w.execute(
            "select count(*) from split_items where date(created_at)=?" , (day,)).fetchone()[0]
        stats["入库书数"] = w.execute("select count(*) from books").fetchone()[0]
        stats["已拆块数"] = w.execute("select count(*) from book_split_done").fetchone()[0]
        w.close()
    except Exception as e:
        stats["统计失败"] = str(e)[:60]
    return lines, memos, stats


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    lines, memos, stats = gather(day)
    if not lines and not memos:
        print("这天没有记录：", day)
        return

    prompt = "日期：%s\n\n【当天的进度行】\n%s\n\n【当天新增的记忆（标题+片段）】\n%s\n\n【库统计】\n%s" % (
        day,
        "\n".join(lines) or "（无）",
        "\n".join(memos) or "（无）",
        "\n".join("%s：%s" % (k, ("{:,}".format(v) if isinstance(v, int) else v)) for k, v in stats.items()),
    )
    text = ask(prompt)
    if not text.strip():
        print("模型没返回内容")
        return

    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "%s.md" % day)
    head = "# %s · 今日简报\n\n> 自动生成 · 素材来自当天的进度行与记忆\n\n" % day
    with open(p, "w", encoding="utf-8") as f:
        f.write(head + text.strip() + "\n")
    print("已写：", p)
    print("字数：", len(text))
    print("-" * 40)
    print(text.strip()[:1200])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
