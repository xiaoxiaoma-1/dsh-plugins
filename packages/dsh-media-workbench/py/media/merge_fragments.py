# -*- coding: utf-8 -*-
"""整理 191 条「书名只剩编号」的记录：
1. 认出来的（道德经/老A官场/县委系列等）合并成整本，补回书名
2. 认不出的零散条目删除（用户 2026-11-05 06:44：太零散太杂乱就删掉）

删前全量备份。
"""
import json
import os
import re
import sqlite3
import time

DB = r"E:\desktop\media\workbench.db"
REC = r"E:\desktop\media\_book_recover.json"
OUT = r"E:\desktop\书库盘点\_recovered_books_20261105"

# 把模型给出的变体名归到主名
CANON = [
    (r'道德经|老子|道经', '道德经'),
    (r'老A|老a|老处长.*混官场', '老A处长教你混官场'),
    (r'县委大院|县委办公室|县委办|县府办主任', '县委大院'),
    (r'老A.*回忆录|老A.*官场笔记', '老A官场回忆录'),
]


def canon(name):
    for pat, main in CANON:
        if re.search(pat, name):
            return main
    return name


def main():
    os.makedirs(OUT, exist_ok=True)
    data = json.load(open(REC, encoding='utf-8'))
    conn = sqlite3.connect(DB, timeout=180)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma busy_timeout = 180000")

    # 重建分组（按主名）
    groups = {}
    for book, members in data['groups'].items():
        main_name = canon(book)
        groups.setdefault(main_name, []).extend(members)
    unknown = data['unknown']

    def full_rows(ids):
        ph = ','.join('?' * len(ids))
        b = [dict(x) for x in conn.execute('select * from books where id in (%s)' % ph, ids)]
        c = [dict(x) for x in conn.execute('select * from book_chunks where book_id in (%s)' % ph, ids)]
        s = [dict(x) for x in conn.execute('select * from split_items where post_id in (%s)' % ph, ids)]
        return b, c, s

    all_ids = [m['id'] for ms in groups.values() for m in ms] + [u['id'] for u in unknown]
    books, chunks, splits = full_rows(all_ids)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    p = os.path.join(OUT, 'recovered_%s.json' % stamp)
    json.dump({'at': stamp, 'books': books, 'chunks': chunks, 'split_items': splits,
               'groups': list(groups.keys()), 'unknown': len(unknown)},
              open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    print('备份 %s（%.1f MB）' % (p, os.path.getsize(p) / 1048576))
    print('  书 %d / 块 %d / 拆解 %d' % (len(books), len(chunks), len(splits)))

    cur = conn.cursor()
    merged = 0
    for main_name, ms in groups.items():
        ids = [m['id'] for m in ms]
        keep = ids[0]                       # 留第一条当合并后的书
        cur.execute("update books set title=?, pages=(select count(distinct page_from) from book_chunks where book_id in (%s)) where id=?"
                    % ','.join('?' * len(ids)), [main_name] + ids + [keep])
        for other in ids[1:]:
            cur.execute("update book_chunks set book_id=? where book_id=?", (keep, other))
            cur.execute("update split_items set post_id=? where post_id=?", (keep, other))
            cur.execute("delete from books where id=?", (other,))
        merged += 1
        print('  合并《%s》：%d 条 → 1 条' % (main_name, len(ids)))

    if unknown:
        uids = [u['id'] for u in unknown]
        ph = ','.join('?' * len(uids))
        cur.execute('delete from split_items where post_id in (%s)' % ph, uids)
        cur.execute('delete from book_chunks where book_id in (%s)' % ph, uids)
        cur.execute('delete from books where id in (%s)' % ph, uids)
        print('  删除认不出的零散条目：%d 条' % len(uids))

    conn.commit()
    print('\n合并 %d 本，删除 %d 条零散记录' % (merged, len(unknown)))
    print('剩余书：%d 本' % conn.execute('select count(*) from books').fetchone()[0])
    conn.close()


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    main()
