# -*- coding: utf-8 -*-
"""删掉书库里的 11 本小说（含宋明风云），删前全量备份成 json。

用户 2026-11-05 05:46：「删掉删掉删掉这些11本小说」「什么宋明风云历史小说，我不要小说啊」
备份原则：删前先导出，可恢复。
"""
import json
import os
import sqlite3
import time

DB = r"E:\desktop\media\workbench.db"
OUT_DIR = r"E:\desktop\书库盘点\_deleted_novels_20261105"

NOVEL_KW = ['后宫小说', '言情', '三生三世', '天子谋', '再嫁（全两册）', '首席幕僚',
            '重生之女帝', '省长亲信', '谋天子', '宋明风云', '掌上明珠']


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma busy_timeout = 120000")

    rows = [dict(r) for r in conn.execute("select * from books")]
    targets = [r for r in rows if any(k in (r['title'] or '') for k in NOVEL_KW)]
    if not targets:
        print('没找到要删的小说')
        return
    print('要删 %d 本' % len(targets))

    stamp = time.strftime('%Y%m%d-%H%M%S')
    pack = {'deleted_at': stamp, 'books': [], 'chunks': [], 'split_items': [], 'split_done': []}
    for r in targets:
        bid = r['id']
        print('  备份', (r['title'] or '')[:40])
        pack['books'].append(r)
        pack['chunks'] += [dict(x) for x in conn.execute(
            'select * from book_chunks where book_id=?', (bid,))]
        pack['split_items'] += [dict(x) for x in conn.execute(
            'select * from split_items where post_id=?', (bid,))]
        pack['split_done'] += [dict(x) for x in conn.execute(
            'select * from book_split_done where chunk_id in (select id from book_chunks where book_id=?)', (bid,))]

    path = os.path.join(OUT_DIR, 'novels_backup_%s.json' % stamp)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(pack, f, ensure_ascii=False)
    size_mb = os.path.getsize(path) / 1048576
    print('备份写入 %s（%.1f MB）' % (path, size_mb))
    print('  书 %d / 块 %d / 拆解 %d / 完成标记 %d' % (
        len(pack['books']), len(pack['chunks']), len(pack['split_items']), len(pack['split_done'])))

    # 备份确认写成功才删
    if size_mb < 0.01:
        print('备份文件异常小，放弃删除')
        return

    ids = [r['id'] for r in targets]
    ph = ','.join('?' * len(ids))
    cur = conn.cursor()
    cur.execute('delete from split_items where post_id in (%s)' % ph, ids)
    n_split = cur.rowcount
    cur.execute('delete from book_split_done where chunk_id in (select id from book_chunks where book_id in (%s))' % ph, ids)
    n_done = cur.rowcount
    cur.execute('delete from book_chunks where book_id in (%s)' % ph, ids)
    n_chunks = cur.rowcount
    cur.execute('delete from books where id in (%s)' % ph, ids)
    n_books = cur.rowcount
    conn.commit()

    print('已删除：书 %d / 块 %d / 拆解 %d / 完成标记 %d' % (n_books, n_chunks, n_split, n_done))
    print('剩余书总数:', conn.execute('select count(*) from books').fetchone()[0])
    print('剩余拆解:', conn.execute('select count(*) from split_items').fetchone()[0])
    conn.close()


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
