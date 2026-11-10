# -*- coding: utf-8 -*-
"""干货碎片 → 打法卡（可复用的流程，不是又一条道理）。

设计（2026-11-05 定）：
- 一张卡 6 字段：名字 / 什么时候用 / 步骤(3-5) / 前提 / 反例 / 来源
- 同一主题下干货 ≥3 条才蒸，不足显示「素材不足 N/3」，不硬凑
- 每条卡必须能溯源到原文（sources 存 split_items.id）

用法：
  python make_playbook.py --source live --min 3 --apply
  python make_playbook.py --source all  --min 3 --apply
"""
import json
import re
import sqlite3
import sys
import time
import urllib.request

DB = r"E:\desktop\media\workbench.db"
GATEWAY = "http://127.0.0.1:8326/v1/chat/completions"
KEYFILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

SYS = """你是内容方法论编辑。下面是一批「干货」碎片，都来自同一位博主的口播/直播。
碎片是「一句话道理」，现在要把它们蒸成「打法卡」——能照着做的一组动作。

硬要求：
- 只蒸「素材够」的主题：同一主题至少 3 条碎片才做，不足的直接丢掉，不要硬凑。
- 步骤必须是有顺序的动作，每条一句话、可执行。不要写「要有耐心」这种。
- 名字要短、像术语，比如「三层筛选选题法」。
- 反例写「什么情况下别用」，不是写缺点。
- sources 里填你实际用到的**原文片段**（每条至少 12 个字，直接抄列表里的原话），不要填编号。
  填编号容易数错，填原文片段才能对得上、能回溯。
- 只输出 JSON 数组，不要解释。格式：
[{"name":"","when":"","steps":["",""],"premise":"","counter":"","sources":["原文片段1","原文片段2"],"topic":""}]"""


def key():
    return open(KEYFILE, encoding="utf-8").read().strip()


def call(prompt, timeout=180):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 3000,
    }).encode("utf-8")
    req = urllib.request.Request(GATEWAY, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key(),
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    c = j["choices"][0]["message"].get("content")
    if not c:
        raise RuntimeError("empty content")
    return c


def parse(raw):
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        return []


def ensure(conn):
    conn.execute("""create table if not exists playbook_cards(
        id text primary key, name text, when_use text, steps text,
        premise text, counter text, sources text, topic text,
        source_kind text, created_at text)""")
    conn.commit()


def main():
    source = "live"
    if "--source" in sys.argv:
        source = sys.argv[sys.argv.index("--source") + 1]
    min_n = 3
    if "--min" in sys.argv:
        min_n = int(sys.argv[sys.argv.index("--min") + 1])
    apply_ = "--apply" in sys.argv

    conn = sqlite3.connect(DB, timeout=90)
    conn.execute("pragma busy_timeout = 90000")
    ensure(conn)

    if source == "all":
        rows = conn.execute(
            "select id, board, note, text from split_items where board='dry'"
            " order by created_at desc limit 400").fetchall()
    else:
        rows = conn.execute(
            "select id, board, note, text from split_items where board='dry' and source=?"
            " order by created_at desc limit 200", (source,)).fetchall()

    if len(rows) < min_n:
        print(json.dumps({'ok': False, 'error': '干货只有 %d 条，不够 %d' % (len(rows), min_n)}, ensure_ascii=False))
        return

    lines = []
    for i, (sid, board, note, text) in enumerate(rows, 1):
        lines.append('%d. [%s] %s' % (i, note or '', (text or '')[:160]))
    prompt = "共 %d 条干货碎片：\n\n%s" % (len(rows), "\n".join(lines))

    print("调模型蒸卡，碎片 %d 条…" % len(rows))
    raw = call(prompt)
    cards = parse(raw)
    print("模型给出 %d 张卡" % len(cards))

    if not apply_:
        for c in cards[:5]:
            print(json.dumps(c, ensure_ascii=False, indent=1)[:600])
        print("\n(--apply 才写库)")
        return

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    n = 0
    for c in cards:
        try:
            name = str(c.get('name', '')).strip()
            steps = c.get('steps') or []
            srcs = c.get('sources') or []
            if not name or len(steps) < 2:
                continue
            ids = []
            used = []
            for s in srcs:
                frag = str(s or '').strip()
                if len(frag) < 8:
                    continue
                # 用原文片段反查 split_items.id，对不上就说明模型编了，这条不记
                hit = conn.execute(
                    "select id, text from split_items where board='dry' and instr(text, ?) > 0"
                    " order by length(id) limit 1", (frag[:40],)).fetchone()
                if hit:
                    ids.append(hit[0])
                    used.append(frag[:40])
            cid = 'pb_%s_%d' % (re.sub(r'\W+', '', name)[:20], int(time.time() * 1000) % 100000)
            conn.execute(
                "insert or replace into playbook_cards(id,name,when_use,steps,premise,counter,sources,topic,source_kind,created_at)"
                " values(?,?,?,?,?,?,?,?,?,?)",
                (cid, name, str(c.get('when', ''))[:300],
                 json.dumps(steps, ensure_ascii=False),
                 str(c.get('premise', ''))[:300], str(c.get('counter', ''))[:300],
                 json.dumps(ids, ensure_ascii=False), str(c.get('topic', ''))[:40],
                 source, now))
            n += 1
        except Exception as e:
            print("  跳过一张:", str(e)[:80])
    conn.commit()
    conn.close()
    print("写入 %d 张打法卡" % n)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding="utf-8")
    main()
