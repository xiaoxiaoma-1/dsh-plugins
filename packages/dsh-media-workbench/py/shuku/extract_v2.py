# -*- coding: utf-8 -*-
"""六板块拆解 v3：片段 + 可迁移性三问 + 文言配译文 + 分板块门槛。

写入独立表 split_items_v3，不动正在跑的 v1。
用法：python extract_v2.py [块数] [并发]
"""
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SRC = r"file:E:\desktop\media\workbench.db?mode=ro"
DB = r"E:\desktop\书库盘点\pilot_v2.db"
GATEWAY = "http://127.0.0.1:8326/v1/chat/completions"
KEY = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

PASS = {"hook": 7, "dry": 6, "case": 7, "quote": 8, "avoid": 6}

SYS = """你是中文内容编辑，从书籍段落里挑出能直接用于短视频/文案的素材。

## 先过三问，过不了就跳过

拿到一条候选，依次问：
1. **脱离这本书，这句话还能用在别的场景吗？** 不能就扔掉——那是台词、情节、历史叙述。
2. **没读过这本书的人，看得懂吗？** 看不懂就给出准确现代译文，给不出就扔掉。
3. **读者拿走这条，能解决什么写作问题？** 说不清就扔掉。

## 以下一律不算，直接跳过

- 历史人物台词、对话（不管多精彩）
- 政论、方针、会议决议、讲话（"我们应当""必须坚持"）
- 新闻报道、赛事、行情复盘、基金产品介绍
- 文献考据、版本说明、译者按、作者生平
- 纯场面、景物、心理描写
- 只有情绪没有判断的感叹

## 每条必须回答「读者能拿走什么」

动笔打分前，先在心里回答一句：**读者拿走这条，能解决什么写作问题？**
- 答得出来且具体（"写开头时能当钩子""讲道理时能当论据""结尾能收一句"）→ 才进入打分。
- 答不出来，或只能答"涨知识""有启发""写得漂亮"→ **直接丢弃，不输出**。

## 反例对照（这些不要）

**注意不要过度泛化**：不要因为下面几条不合格，就把真正的好句子也砍掉。
❌ 「康熙下谕："此出自朕意，他人何罪？"」——换个场景就没用了，是台词。
❌ 「男孩子汉大丈夫，跪天跪地跪父母」——口号，读者拿走用不上。
❌ 「何心隐说："我祖师爷王阳明说，书院的意义是弥补官学的不足"」——人物对白，不看书不知道谁在说。

**给正例会误导你照着表面特征匹配，所以这里不给正例。只用一句话判断：去掉人物、场景、上下文之后，这句话还立不立得住。**

## 以下几种常见误判，特别注意

- 古人说的话里，**大量是台词和人名对话**。看到"某某曰""某某说"先怀疑，只有内容是**通用规律**才可留。
- 俗语、成语、格言（"水至清则无鱼""冰冻三尺非一日之寒"）**不算金句**——人人都知道，拿走没增量。
- 小说里的心理描写、外貌描写、气氛描写，**一律不算**。
- 单句孤立地"看着有道理"，但说不出能用在什么写作位置，也不算。

## 以下是古文但可以收

古文不是问题。只要能给出准确现代译文、且脱开原文仍然成立，就收，译文放 translation 字段。

## 录入单位是片段

一条可以 1–5 句、30–200 字。唯一要求是「自足」：单独拿出来，不查原文也能看懂、能用。

## 六类与及格线

1. **hook 钩子**（≥7）：**判断标准只有一个：这句话放到视频开头，能不能让人眼前一亮、想往下看？**
   - **不限它在书里的位置**——段首、段中、结尾、对话里都行，只要能单拎出来放开头有力。
   - 10 分＝一开口就有信息缺口或反常识，非想知道下文；7 分＝有具体场景、数字或冲突，能勾人；≤5 分＝陈述句，没有张力。
   - 注意：要的不是"段落的第一句"，是"能当视频第一句的那句"。
2. **dry 干货**（≥6）：能照做的道理、步骤。10 分＝动作＋判断标准；6 分＝有明确判断但空泛；≤4 分＝常识。
3. **case 案例**（≥7）：证明观点的具体事例。10 分＝主角＋动作＋结果数字；7 分＝有例有果缺细节；≤4 分＝场面描写。
4. **quote 金句**（≥8）：脱离原文让人「原来是这样」。10 分＝反常识判断；8 分＝有洞察会点头；≤6 分＝文笔好没信息。
5. **avoid 避坑**（≥6）：读者可能犯的具体错误。10 分＝错动作＋后果＋改法；6 分＝指出具体错误；≤4 分＝鸡汤。

（书籍来源不产出问答：书里只有人物对白，没有真问答。）

## 文言处理

古文可以收，但**必须给出准确的现代汉语翻译**，放在 translation 字段。给不出就不要这条。白话文条目的 translation 填空字符串。

## 输出

只输出达到及格线的条目。JSON 数组，不要解释、不要 markdown 代码块：
[{"board":"quote","score":9,"text":"原文片段","translation":"现代汉语译文，白话文留空","note":"不超过18字"}]
一段最多 3 条。没有达标的输出 []。"""


def key():
    return open(KEY, encoding="utf-8").read().strip()


def ask(content, title, timeout=180):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": "书名：《%s》\n\n段落：\n%s" % (title[:40], content[:2000])}],
        "temperature": 0.2, "max_tokens": 1600,
    }).encode("utf-8")
    req = urllib.request.Request(GATEWAY, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    return j["choices"][0]["message"].get("content") or ""


RESCORE_SYS = """你是严格的短视频编导。给你一句话，判断它单独放到视频开头，能不能让人眼前一亮、想往下看。
只回一个 1-10 的整数，不要任何解释、不要标点。
9-10：一开口就有反常识或信息缺口，非想知道下文
7-8：有具体场景、数字或冲突，能勾人
5-6：有信息但平淡
1-4：废话、俗语、需要上下文才知道在说什么、人物台词"""

QUOTE_RESCORE_SYS = """你是内容编辑，判断一段话能不能当「金句」用。

金句只有一个问题：**这段话好不好？**
好的方式有三种，中一种就算金句：
1. **说得对**——把深刻的道理浓缩在一两句话里，读完心里一动
2. **说得好**——表达精彩，用词有味道，让人想抄下来
3. **说得中**——打动人，戳中某种共同的感受

不算金句的（给 1-3 分）：
- 平铺直叙的描述、叙述、流水账
- 公文、通知、流程说明、会议记录
- 没有内容的套话、口水话
- 必须知道上下文才懂的台词（不知道谁在跟谁说）
- 纯数据、纯术语罗列

评分：
10：两种好都占了，或者一种好到了极致
8-9：明显属于其中一种好，读完能记住
6-7：有点意思，但不够
1-5：属于上面不算的那几类

只回一个 1-10 的整数，不要解释。"""


def rescore(text, kind="hook"):
    sys_prompt = QUOTE_RESCORE_SYS if kind == "quote" else RESCORE_SYS
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": text[:400]}],
        "temperature": 0.0, "max_tokens": 12,
    }).encode("utf-8")
    req = urllib.request.Request(GATEWAY, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key()})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.loads(r.read().decode("utf-8"))
    t = (j["choices"][0]["message"].get("content") or "").strip()
    m = re.search(r"\d+", t)
    return int(m.group(0)) if m else 0


def parse(text):
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    m = re.search(r"\[.*\]", t, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return []
    out = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        b = str(x.get("board", "")).strip().lower()
        try:
            sc = float(x.get("score", 0))
        except Exception:
            sc = 0
        tx = str(x.get("text", "")).strip()
        tr = str(x.get("translation", "")).strip()
        nt = str(x.get("note", "")).strip()[:40]
        if b in PASS and tx and len(tx) >= 12 and sc >= PASS[b]:
            out.append((b, sc, tx, tr, nt))
    return out[:3]


def work(row):
    cid, bid, title, content = row
    try:
        items = parse(ask(content, title))
        kept = []
        for b, sc, tx, tr, nt in items:
            if b == "hook":
                # 钩子：按"放视频开头能不能抓人"复评，≥8 留
                if rescore(tx, "hook") >= 8:
                    kept.append((b, sc, tx, tr, nt))
            elif b == "quote":
                # 金句：按"能不能让人原来如此"复评，≥7 留
                if rescore(tx, "quote") >= 7:
                    kept.append((b, sc, tx, tr, nt))
            else:
                kept.append((b, sc, tx, tr, nt))
        return (cid, bid, title, kept, None)
    except Exception as e:
        return (cid, bid, title, [], str(e)[:80])


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    src = sqlite3.connect(SRC, uri=True, timeout=30)
    wdb = sqlite3.connect(r"E:\desktop\media\workbench.db", timeout=60)
    wdb.execute("create table if not exists v6_done(chunk_id text primary key, at text)")
    wdb.commit()
    done = set(x[0] for x in wdb.execute("select chunk_id from v6_done"))
    c = sqlite3.connect(DB, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""create table if not exists split_items_v3(
        id text primary key, book_id text, title text, board text, score real,
        text text, translation text, note text, at text)""")
    c.commit()
    rows = src.execute("""select ch.id, ch.book_id, b.title, ch.content
        from book_chunks ch join books b on b.id=ch.book_id
        where length(ch.content)>=200
          and b.category not in ('冥想与身心','身心与养生','待定')
          and b.title not like '%小说%'
        order by random()""").fetchall()
    rows = [r for r in rows if r[0] not in done][:n]
    print("抽 %d 块，并发 %d" % (len(rows), workers), flush=True)

    ok = total = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, (cid, bid, title, items, err) in enumerate(ex.map(work, rows), 1):
            if err:
                continue
            for k, (board, sc, tx, tr, nt) in enumerate(items):
                c.execute("insert or replace into split_items_v3 values(?,?,?,?,?,?,?,?,datetime('now'))",
                          ("%s_%s_%d" % (cid, board, k), bid, title, board, sc, tx, tr, nt))
                total += 1
            wdb.execute("insert or ignore into v6_done values(?,datetime('now'))", (cid,))
            ok += 1
            if i % 50 == 0:
                c.commit()
                print("  %d/%d 块，出 %d 条，均 %.2fs/块" % (i, len(rows), total, (time.time() - t0) / i), flush=True)
    c.commit()
    wdb.commit()
    wdb.close()
    print("\n完成：%d 块，%d 条，%.1f 分钟，每块 %.2f 条（v2 是 1.16）"
          % (ok, total, (time.time() - t0) / 60, total / max(ok, 1)))
    c.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
