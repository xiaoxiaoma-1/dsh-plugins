# -*- coding: utf-8 -*-
"""把刚才删掉的零散条目原样恢复回来。

用户 2026-11-05 06:47：「先把那些刚才删掉的全部恢复过来吧。等这些 OCR 的内容全部转移完了之后，我们再弄吧」
理由：担心那些单页条目是「还没 OCR 完的书」散开形成的，不是垃圾。

做法：从备份 json 里取出当前库已经不存在的 book_id，原样插回 books / book_chunks / split_items。
"""
import json
import os
import sqlite3

DB = r"E:\desktop\media\workbench.db"
BAK_DIR = r"E:\desktop\书库盘点\_recovered_books_20261105"


def main():
    # 取最新备份
    files = sorted(f for f in os.listdir(BAK_DIR) if f.startswith('recovered_') and f.endswith('.json'))
    if not files:
        print('找不到备份')
        return
    path = os.path.join(BAK_DIR, files[-1])
    print('用备份:', path)
    pack = json.load(open(path, encoding='utf-8'))

    conn = sqlite3.connect(DB, timeout=180)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma busy_timeout = 180000")

    have = {r[0] for r in conn.execute('select id from books')}
    miss_books = [b for b in pack['books'] if b['id'] not in have]
    print('备份里的书 %d 本，当前库缺失 %d 本' % (len(pack['books']), len(miss_books)))

    if not miss_books:
        print('没有需要恢复的')
        return

    miss_ids = {b['id'] for b in miss_books}
    miss_chunks = [c for c in pack['chunks'] if c.get('book_id') in miss_ids]
    miss_splits = [s for s in pack['split_items'] if s.get('post_id') in miss_ids]

    cur = conn.cursor()
    # 原样插回（列名从字典 key 取）
    for b in miss_books:
        cols = list(b.keys())
        cur.execute('insert or replace into books(%s) values(%s)'
                    % (','.join(cols), ','.join('?' * len(cols))), [b[c] for c in cols])
    for c in miss_chunks:
        cols = list(c.keys())
        cur.execute('insert or replace into book_chunks(%s) values(%s)'
                    % (','.join(cols), ','.join('?' * len(cols))), [c[k] for k in cols])
    for s in miss_splits:
        cols = list(s.keys())
        cur.execute('insert or replace into split_items(%s) values(%s)'
                    % (','.join(cols), ','.join('?' * len(cols))), [s[k] for k in cols])
    conn.commit()

    print('已恢复：书 %d / 块 %d / 拆解 %d' % (len(miss_books), len(miss_chunks), len(miss_splits)))
    print('当前书总数:', conn.execute('select count(*) from books').fetchone()[0])
    conn.close()


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
