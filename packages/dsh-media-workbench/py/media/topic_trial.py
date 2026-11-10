# -*- coding: utf-8 -*-
"""书库标签试跑：抽 20 本，让模型自己归纳「话题」和「内容类型」，再把话题汇总出来。

为什么要它自己归纳：上次我凭空编话题词表，用户说「你结合过我的书稿吗」。
这次反过来——先让模型从真实书里长出话题词，再汇总，用户看了再定词表。
"""
import json
import random
import sqlite3
import urllib.request

DB = r"E:\desktop\media\workbench.db"
GATEWAY = "http://127.0.0.1:8326/v1/chat/completions"
KEYFILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

SYS = """你在给一个内容创作者的书库打标签。他会说「我想写一篇关于 X 的内容」，系统要能靠标签把相关的书捞出来。

对每一本书，给出：
1. topic（话题）：这本书能让读者学到「关于什么的认知」。用 2-6 个字，要具体，不要用「商业」「心理」这种学科名。可以给 1-3 个。
   好例子：搞钱思路、带团队、原生家庭、底层思维、说话分寸、看人识人
   坏例子：商业、心理、哲学（太泛，没法用来找料）
2. kind（内容类型）：这本书主要是什么形态。从这四个里选 1-2 个：
   - 观点类（讲一种看法/立场）
   - 方法类（给步骤/做法）
   - 案例类（讲发生过的具体事）
   - 数据类（有数字、研究、统计）

只输出 JSON 数组，不要解释。格式：
[{"i":1,"topic":["搞钱思路"],"kind":["方法类"],"why":"一句话说为什么这么打"}]"""


def key():
    return open(KEYFILE, encoding="utf-8").read().strip()


def call(prompt, timeout=180):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}],
        "temperature": 0.3, "max_tokens": 2000,
    }).encode("utf-8")
    req = urllib.request.Request(GATEWAY, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    c = j["choices"][0]["message"].get("content")
    if not c:
        raise RuntimeError("empty content")
    return c


def parse(raw):
    import re
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        return []


def main():
    conn = sqlite3.connect(DB, timeout=60)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "select id,title from books where id in (select distinct book_id from book_chunks)")]
    random.seed(20261105)
    sample = random.sample(rows, min(20, len(rows)))

    lines = []
    for i, r in enumerate(sample, 1):
        ch = conn.execute(
            "select content from book_chunks where book_id=? order by page_from limit 1", (r['id'],)).fetchone()
        head = (ch['content'] if ch else '')[:700].replace('\n', ' ')
        lines.append('%d. 《%s》\n   开头：%s' % (i, (r['title'] or '')[:40], head))

    prompt = '共 %d 本书，请逐本打标签：\n\n%s' % (len(sample), '\n'.join(lines))
    print('抽了 %d 本，调模型打标签…' % len(sample))
    cards = parse(call(prompt))
    print('返回 %d 条\n' % len(cards))

    out = []
    for c in cards:
        i = c.get('i')
        if not isinstance(i, int) or not (1 <= i <= len(sample)):
            continue
        r = sample[i - 1]
        out.append({
            'title': r['title'][:46], 'topics': c.get('topic') or [],
            'kinds': c.get('kind') or [], 'why': c.get('why', ''),
        })

    for o in out:
        print('《%s》' % o['title'])
        print('  话题:', ' / '.join(o['topics']) or '—', '| 类型:', ' / '.join(o['kinds']) or '—')
        if o['why']:
            print('  ', o['why'][:60])

    # 汇总所有话题词，看哪些反复出现
    from collections import Counter
    cnt = Counter()
    for o in out:
        for t in o['topics']:
            cnt[t] += 1
    print('\n=== 本批出现的话题词（频次）===')
    for w, n in cnt.most_common():
        print('  %s ×%d' % (w, n))

    with open(r'E:\desktop\media\_topic_trial.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\n已写 E:\\desktop\\media\\_topic_trial.json')


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
