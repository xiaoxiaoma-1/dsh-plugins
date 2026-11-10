# -*- coding: utf-8 -*-
"""稿库「书」来源查询：列书 / 读全文 / 搜关键词。

用法：
  python books_query.py list --limit 60 [--q 关键词] [--category 分类]
  python books_query.py book --id book_xxx      # 读 E:\\wengao_md\\<书名>.md；没有就拼前几块
"""
import json
import os
import sqlite3
import sys

DB = r'E:\desktop\media\workbench.db'
MD_DIR = r'E:\wengao_md'


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def list_books(limit=60, q='', category=''):
    c = conn()
    where = []
    args = []
    if q:
        where.append('(b.title like ? or b.category like ?)')
        args += ['%' + q + '%', '%' + q + '%']
    if category:
        where.append('b.category = ?')
        args.append(category)
    sql = ('select b.id, b.title, b.pages, b.category, b.ocr_state, b.created_at, '
           'count(k.id) as chunks '
           'from books b left join book_chunks k on k.book_id=b.id ')
    if where:
        sql += 'where ' + ' and '.join(where) + ' '
    sql += "group by b.id having b.ocr_state='done' order by b.created_at desc limit ?"
    args.append(limit)
    rows = [dict(r) for r in c.execute(sql, args)]
    cats = [dict(r) for r in c.execute(
        "select category, count(*) n from books where ocr_state='done' group by category "
        "order by n desc")]
    total = c.execute("select count(*) from books where ocr_state='done'").fetchone()[0]
    c.close()
    return {'ok': True, 'total': total, 'list': rows, 'categories': cats}


def read_book(bid='', title=''):
    c = conn()
    row = None
    if bid:
        row = c.execute('select id,title,pages,category from books where id=?', (bid,)).fetchone()
    if row is None and title:
        row = c.execute('select id,title,pages,category from books where title=?', (title,)).fetchone()
    if row is None:
        c.close()
        return {'ok': False, 'error': '找不到这本书'}
    bid, title, pages, category = row['id'], row['title'], row['pages'], row['category']
    text = ''
    md = os.path.join(MD_DIR, title + '.md')
    if os.path.exists(md):
        try:
            with open(md, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        except OSError:
            text = ''
    if not text:
        chunks = c.execute(
            'select content from book_chunks where book_id=? order by page_from', (bid,)).fetchall()
        text = '\n\n'.join(r['content'] for r in chunks)
    c.close()
    return {'ok': True, 'id': bid, 'title': title, 'pages': pages,
            'category': category or '', 'chars': len(text), 'text': text}


def main():
    argv = sys.argv[1:]
    cmd = argv[0] if argv else 'list'
    if cmd == 'book':
        bid = ''
        title = ''
        for i, a in enumerate(argv):
            if a == '--id' and i + 1 < len(argv):
                bid = argv[i + 1]
            if a == '--title' and i + 1 < len(argv):
                title = argv[i + 1]
        out = read_book(bid, title)
    else:
        limit, q, category = 60, '', ''
        for i, a in enumerate(argv):
            if a == '--limit' and i + 1 < len(argv):
                limit = int(argv[i + 1])
            if a == '--q' and i + 1 < len(argv):
                q = argv[i + 1]
            if a == '--category' and i + 1 < len(argv):
                category = argv[i + 1]
        out = list_books(limit, q, category)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
