# -*- coding: utf-8 -*-
"""把直播稿按「场」合并：同一主播同一场的多个分段，拼成一篇完整逐字稿。

为什么会碎：录制器开了 1800 秒分段，加上中途重启了 3 次，所以一场直播变成好几篇，
而且重启后从头接流，内容有重叠。

合并规则：
1. 按主播分组
2. 组内按标题里的时间戳排序（标题形如 百万大猫_2026-11-05_02-22-00_002）
3. 拼接时去掉重叠：找前文末尾与后文开头的最长公共段
4. 写回 posts，原分段删除（连带它们的拆解条目），删前备份
"""
import json
import os
import re
import sqlite3
import time

DB = r"E:\desktop\media\workbench.db"
OUT_DIR = r"E:\desktop\media\_merge_live_backup"


def overlap_len(a, b, cap=3000):
    """a 的末尾和 b 的开头最长重合多少字"""
    maxk = min(len(a), len(b), cap)
    for k in range(maxk, 30, -1):
        if a[-k:] == b[:k]:
            return k
    return 0


def merge(texts):
    out = texts[0]
    for t in texts[1:]:
        if t in out:
            continue
        k = overlap_len(out, t)
        out += t[k:]
    return out


def parse_ts(title):
    m = re.search(r'(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})', title or '')
    if m:
        return m.group(1) + ' ' + ':'.join(m.group(2, 3, 4))
    return ''


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma busy_timeout = 120000")

    rows = [dict(r) for r in conn.execute(
        "select id, author, date, text from posts where kind='live' order by created_at")]
    if not rows:
        print('没有直播稿')
        return

    # 按主播分组
    groups = {}
    for r in rows:
        a = r['author'] or '未知主播'
        # author 形如「直播：百万大猫 · 百万大猫_2026-11-05_02-22-00_000」
        name = a.split('·')[0].replace('直播：', '').strip() or '未知主播'
        ts = parse_ts(a)
        groups.setdefault(name, []).append((ts, r))

    stamp = time.strftime('%Y%m%d-%H%M%S')
    backup_path = os.path.join(OUT_DIR, 'before_merge_%s.json' % stamp)
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print('原稿备份:', backup_path)

    made = []
    for name, items in groups.items():
        items.sort(key=lambda x: x[0])
        texts = [it[1]['text'] or '' for it in items]
        merged = merge(texts)
        date = items[0][1]['date'] or time.strftime('%Y-%m-%d')
        new_id = 'live_merged_%s_%s' % (re.sub(r'\W+', '', name)[:12], stamp)
        made.append({
            'id': new_id, 'author': '直播：' + name, 'date': date, 'text': merged,
            'parts': len(items), 'src_chars': sum(len(t) for t in texts), 'chars': len(merged),
        })
        conn.execute("insert or replace into posts(id,author,date,kind,text,created_at)"
                     " values(?,?,?,?,?,datetime('now'))",
                     (new_id, '直播：' + name, date, 'live', merged))
        print('  合并 %s：%d 段 %d 字 → %d 字' % (name, len(items), sum(len(t) for t in texts), len(merged)))

    # 删除原分段（连带拆解）
    ids = [r['id'] for r in rows]
    ph = ','.join('?' * len(ids))
    cur = conn.cursor()
    cur.execute('delete from split_items where post_id in (%s)' % ph, ids)
    n_sp = cur.rowcount
    cur.execute('delete from posts where id in (%s)' % ph, ids)
    n_po = cur.rowcount
    conn.commit()
    print('已删原分段：稿 %d 篇、拆解 %d 条' % (n_po, n_sp))
    print('合并后直播稿:', conn.execute("select count(*) from posts where kind='live'").fetchone()[0], '篇')
    conn.close()

    with open(os.path.join(OUT_DIR, 'merged_%s.json' % stamp), 'w', encoding='utf-8') as f:
        json.dump(made, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
