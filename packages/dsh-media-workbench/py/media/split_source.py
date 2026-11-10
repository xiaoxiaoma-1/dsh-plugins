# -*- coding: utf-8 -*-
"""给一条拆解条目找回它的原文出处。

为什么需要：split_items 里有两种来源
- 书：id = "<book_id>_c<块号>_<board>_<k>"，原文在 book_chunks.content
- 稿：id = "<post_id>_<board>_<k>"，原文在 posts.text

旧的 /api/dsh-media/post 只查 posts 表，所以书来源（约占 57%）全部点不开。

用法：python split_source.py <split_item_id>
"""
import json
import sqlite3
import sys

DB = r"E:\desktop\media\workbench.db"

BOARD_CN = {"hook": "钩子", "dry": "干货", "case": "案例",
            "quote": "金句", "avoid": "避坑", "qa": "问答"}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'ok': False, 'error': 'missing id'}, ensure_ascii=False))
        return
    sid = sys.argv[1]

    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "select id, post_id, board, text, note, date, source from split_items where id=?",
        (sid,)).fetchone()
    if not row:
        print(json.dumps({'ok': False, 'error': '这条拆解不在库里：' + sid}, ensure_ascii=False))
        return

    # id 去掉末尾两段（板块 + 序号），剩下的可能是 chunk_id，也可能是 post_id
    parts = sid.rsplit('_', 2)
    base = parts[0] if len(parts) == 3 else sid

    out = {
        'ok': True,
        'board': row['board'],
        'boardCn': BOARD_CN.get(row['board'], row['board']),
        'quote': row['text'] or '',
        'note': row['note'] or '',
        'date': row['date'] or '',
    }

    # 1) 先当书块查
    chunk = conn.execute(
        "select c.id, c.book_id, c.content, c.page_from, b.title from book_chunks c"
        " left join books b on b.id=c.book_id where c.id=?", (base,)).fetchone()
    if chunk:
        out.update({
            'kind': 'book',
            'title': chunk['title'] or chunk['book_id'],
            'page': chunk['page_from'],
            'text': chunk['content'] or '',
        })
        print(json.dumps(out, ensure_ascii=False))
        return

    # 2) 再当稿子查
    post = conn.execute(
        "select id, author, date, kind, text, url from posts where id=?", (base,)).fetchone()
    if post:
        out.update({
            'kind': post['kind'] or 'post',
            'title': post['author'] or base,
            'date': post['date'] or out['date'],
            'url': post['url'] or '',
            'text': post['text'] or '',
        })
        print(json.dumps(out, ensure_ascii=False))
        return

    # 3) 都找不到：至少把这条原话和说明还给用户，别给空
    out.update({'kind': 'unknown', 'title': base,
                'text': '', 'hint': '这篇原文在库里找不到（可能是旧数据被清理了）'})
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
