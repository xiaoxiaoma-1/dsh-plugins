"""书库全量质量+完整性判定（1451 本）v2

v1 的教训：直接让模型判三档，20 本里 18 本都给 B + 同一句模板理由（塌缩）。
v2 改成：先必须从原文摘 3 条证据原话 → 再给 0-10 素材密度分 → 分数映射档位。
"先引用再判断"能显著压住塌缩，且 evidence 可直接用于人工抽验。

判三件事：
1. material_score 0-10 素材密度 → tier A(>=8) / B(4-7) / C(<=3)
2. intact 完整性：正文是否抽坏
3. kind 形态：book / article / notes / fragments

用法：python quality_tier.py [并发] [--limit=N]
输出：_quality_tier.json（增量落盘，断点续跑）+ book_quality 表
"""
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
OUT = r"E:\desktop\media\_quality_tier.json"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

SYS = "你是中文内容质检员。先摘证据再打分，不空口下结论。只输出 JSON。"

PROMPT = """书名：{title}
页数：{pages}｜总字数：{chars}｜切块数：{chunks}

正文节选（首/中/尾）：
{text}

【第一步：摘证据】从上面节选里各抄一句最能代表这本书内容的原话（必须是原文，不许改写、不许自己编），每条不超过 30 字：
- e1：这本书给的具体方法/步骤（没有就填 null）
- e2：这本书给的具体案例/故事/人名/数据（没有就填 null）
- e3：这本书给的能直接用的一句话观点（没有就填 null）

【第二步：打素材密度分 material_score（0-10）】
问自己：如果我要写一篇稿子，从这本书里能捞出多少**具体可用**的东西？
- 9-10：几乎每页都有可用的方法、案例、数字，随手翻都能抄
- 7-8：大部分章节有具体东西，少量是空话
- 5-6：约一半有具体东西，一半是泛泛道理
- 3-4：少量可用，大部分是叙事/鸡汤/重复
- 1-2：几乎捞不出具体东西，全是道理堆砌
- 0：根本不是内容（纯目录、纯图片说明、纯术语表、PDF排版教程）

⚠️ 打分看"有没有具体东西"，不看"讲得好不好"。讲得朴素但有干货就高分；文笔好但全是空话就低分。
⚠️ 完整出版的书极少是 0 分。名著讲得再抽象，也至少有可引用的观点和人物案例。

【第三步：判断完整性 intact】
- true：段落连续、句子通顺、论述完整
- false：页数很多但正文极少、页码跳跃、大量乱码或图片标记、只剩零星短句拼不成句
（"原文本来就短"的文章/笔记，只要通顺，intact 就是 true）

【第四步：形态 kind】book=成体系书籍｜article=单篇短文｜notes=课程笔记讲义｜fragments=碎片拼不成篇

只输出 JSON：
{{"e1":"原文或null","e2":"原文或null","e3":"原文或null","material_score":0-10,"intact":true|false,"kind":"book|article|notes|fragments","why":"不超过20字"}}"""

_lock = threading.RLock()
_done = 0
_tot = 0
_t0 = 0.0
_fail = 0
_results = {}


def call(title, pages, chars, chunks, text, tries=3):
    body = json.dumps({
        "model": MODEL, "temperature": 0.15, "max_tokens": 420,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": PROMPT.format(
                         title=title, pages=pages, chars=chars, chunks=chunks, text=text)}],
    }).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(
                BASE + "/chat/completions", data=body,
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=90) as r:
                j = json.load(r)
            s = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            s = s[s.find("{"): s.rfind("}") + 1]
            o = json.loads(s)
            try:
                sc = float(o.get("material_score"))
            except (TypeError, ValueError):
                sc = -1
            if not (0 <= sc <= 10):
                raise ValueError("bad score")
            sc = int(round(sc))
            tier = "A" if sc >= 8 else ("B" if sc >= 4 else "C")
            kind = (o.get("kind") or "").strip()
            if kind not in ("book", "article", "notes", "fragments"):
                kind = ""
            ev = []
            for k in ("e1", "e2", "e3"):
                v = o.get(k)
                if isinstance(v, str) and v.strip() and v.strip().lower() != "null":
                    ev.append(v.strip()[:40])
            return {"tier": tier, "score": sc, "intact": bool(o.get("intact")),
                    "kind": kind, "why": str(o.get("why") or "")[:40], "ev": ev}
        except Exception:
            time.sleep(1 + i)
    return {"tier": "", "score": -1, "intact": None, "kind": "", "why": "调用失败", "ev": []}


def work(row):
    global _done, _fail
    o = call(row["title"], row["pages"], row["chars"], row["chunks"], row["excerpt"])
    with _lock:
        _done += 1
        if not o["tier"]:
            _fail += 1
        o.update({"pages": row["pages"], "chars": row["chars"], "chunks": row["chunks"]})
        _results[row["id"]] = o
        if _done % 100 == 0 or _done == _tot:
            el = time.time() - _t0
            eta = el / _done * (_tot - _done) / 60
            print(f"  {_done}/{_tot} | {el/60:.1f} 分 | 剩约 {eta:.1f} 分 | 失败 {_fail}", flush=True)
            if _done % 100 == 0:
                dump()
    return row["id"]


def dump():
    with _lock:
        snap = dict(_results)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False)
    os.replace(tmp, OUT)


def main():
    global _tot, _t0
    workers = 32
    limit = None
    for a in sys.argv[1:]:
        if a.isdigit():
            workers = int(a)
        elif a.startswith("--limit"):
            limit = int(a.split("=")[1])

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            _results.update(json.load(f))
        print(f"续跑：已有 {len(_results)} 本结果")

    books = c.execute("""select b.id, b.title, coalesce(b.pages,0) pages,
                                coalesce(x.n,0) chars, coalesce(x.cnt,0) chunks
                         from books b
                         left join (select book_id, sum(length(content)) n, count(*) cnt
                                    from book_chunks group by book_id) x on x.book_id=b.id""").fetchall()

    rows = []
    for b in books:
        if b["id"] in _results:
            continue
        chs = c.execute("select content from book_chunks where book_id=? order by page_from, id",
                        (b["id"],)).fetchall()
        if not chs:
            continue
        texts = [x["content"] or "" for x in chs]
        n = len(texts)
        # v3 修正：跳过首尾各 4%（封面/版权页/后记广告），避开"正文极少"的假象
        skip = max(1, int(n * 0.04))
        body = texts[skip: max(skip + 1, n - skip)]
        m = len(body)
        picks = [body[int(m * f)] for f in (0.0, 0.2, 0.4, 0.6, 0.8, 0.99)] if m else texts
        seen, uniq = set(), []
        for t in picks:
            if not t:
                continue
            # 明显是封面/版权页/图片页的块跳过（每页只有图片标记或 ISBN 信息）
            low = t.lower()
            junk = low.count("![image block]") * 20 + low.count("isbn") * 30
            if junk > len(t) * 0.25:
                continue
            if t[:50] in seen:
                continue
            seen.add(t[:50])
            uniq.append(t[:700])
        if not uniq:
            uniq = [texts[n // 2][:700]] if texts else []
        rows.append({"id": b["id"], "title": b["title"], "pages": b["pages"],
                     "chars": b["chars"], "chunks": b["chunks"],
                     "excerpt": "\n…\n".join(uniq)[:3200]})
    c.close()
    if limit:
        rows = rows[:limit]

    if rows:
        _tot = len(rows)
        _t0 = time.time()
        print(f"待判定 {_tot} 本｜并发 {workers}", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, rows))
        dump()

    c = sqlite3.connect(DB)
    c.execute("drop table if exists book_quality")
    c.execute("""create table if not exists book_quality(
        book_id text primary key, tier text, score int, intact int, kind text, why text,
        ev text, pages int, chars int, chunks int, judged_at text)""")
    c.execute("""create table if not exists book_metric(
        book_id text primary key, pages int, chars int, chunks int,
        chars_per_page real, updated_at text)""")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    c.execute("delete from book_quality")
    c.execute("delete from book_metric")
    for bid, o in _results.items():
        c.execute("insert or replace into book_quality values(?,?,?,?,?,?,?,?,?,?,?)",
                  (bid, o.get("tier"), o.get("score"), 1 if o.get("intact") else 0,
                   o.get("kind"), o.get("why"), "\n".join(o.get("ev") or []),
                   o.get("pages") or 0, o.get("chars") or 0, o.get("chunks") or 0, now))
    for r in c.execute("""select b.id, coalesce(b.pages,0), coalesce(sum(length(cc.content)),0), count(cc.id)
                          from books b left join book_chunks cc on cc.book_id=b.id
                          group by b.id""").fetchall():
        cpp = (r[2] / r[1]) if r[1] else 0
        c.execute("insert or replace into book_metric values(?,?,?,?,?,?)",
                  (r[0], r[1], r[2], r[3], cpp, now))
    c.commit()
    c.close()

    from collections import Counter
    ok = [o for o in _results.values() if o.get("tier")]
    print("\n完成 %d 本｜失败 %d｜耗时 %.1f 分钟" %
          (len(_results), _fail, (time.time() - _t0) / 60 if _t0 else 0))
    print("分数分布:", sorted(Counter(o["score"] for o in ok).items()))
    print("档位:", Counter(o["tier"] for o in ok).most_common())
    print("完整性:", Counter(o["intact"] for o in ok).most_common())
    print("形态:", Counter(o["kind"] for o in ok).most_common())


if __name__ == "__main__":
    main()
