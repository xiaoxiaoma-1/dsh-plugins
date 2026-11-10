# -*- coding: utf-8 -*-
"""
pool_db.py —— 选题池 + 我的观点（语料库）数据层

设计要点
- 两张表，和稿库（posts / book_chunks）完全分开：我的观点写在这里，永不流进稿库。
- 只做数据读写，不调模型。模型的部分在宿主 index.js。
- 所有命令输出单行 JSON，方便宿主 runPyJson 解析。

命令
  init
  pick --n 24              抽素材给选题生成用（稿库 + 书库随机）
  list [--day YYYY-MM-DD] [--status idea] [--limit 50]
  import                    从 stdin 读 JSON 数组写入选题
  setstatus --id X --status idea|writing|published|dropped
  del --ids a,b,c
  views_list [--limit 50] [--q 关键词]
  views_get --id X
  views_save                从 stdin 读 {id?,kind,topicId,title,content,tags}
  views_review --id X       从 stdin 读 {score,verdict,pros,gaps,questions}
  views_del --ids a,b,c
  stats
"""
import sys, os, json, sqlite3, datetime, random, argparse, uuid

DB = r'E:\desktop\media\workbench.db'

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS pool_topics (
      id TEXT PRIMARY KEY,
      day TEXT NOT NULL,
      board TEXT,
      title TEXT NOT NULL,
      angle TEXT,
      hook TEXT,
      source_kind TEXT,
      source_ref TEXT,
      source_title TEXT,
      dims TEXT,
      score INTEGER DEFAULT 0,
      level TEXT,
      why TEXT,
      status TEXT DEFAULT 'idea',
      created_at TEXT,
      used_at TEXT,
      extra TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pool_day ON pool_topics(day)",
    "CREATE INDEX IF NOT EXISTS idx_pool_status ON pool_topics(status)",
    """
    CREATE TABLE IF NOT EXISTS my_views (
      id TEXT PRIMARY KEY,
      kind TEXT,
      topic_id TEXT,
      title TEXT,
      content TEXT,
      chars INTEGER DEFAULT 0,
      ai_review TEXT,
      status TEXT DEFAULT 'saved',
      tags TEXT,
      created_at TEXT,
      updated_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_views_kind ON my_views(kind)",
]


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def today():
    return datetime.date.today().strftime('%Y-%m-%d')


def conn():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def emit(obj):
    # 统一 UTF-8 输出：Windows 控制台默认 GBK，遇到 emoji（atoms 里有）会直接崩
    s = json.dumps(obj, ensure_ascii=False) + '\n'
    try:
        sys.stdout.buffer.write(s.encode('utf-8'))
        sys.stdout.buffer.flush()
    except Exception:
        try:
            sys.stdout.write(s)
        except Exception:
            sys.stdout.write(json.dumps(obj, ensure_ascii=True) + '\n')


def read_stdin_json():
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    return json.loads(raw)


def rid(prefix='t'):
    return prefix + uuid.uuid4().hex[:12]


# ---------------------------------------------------------------- init
def cmd_init(a):
    c = conn()
    for s in SCHEMA:
        c.execute(s)
    # 老库补 board 列（选题按板块分组是 2026-11-07 加的）
    try:
        cols = [d[1] for d in c.execute('pragma table_info(pool_topics)')]
        if 'board' not in cols:
            c.execute('ALTER TABLE pool_topics ADD COLUMN board TEXT')
    except Exception:
        pass
    c.execute('CREATE INDEX IF NOT EXISTS idx_pool_board ON pool_topics(board)')
    c.commit()
    c.close()
    emit({'ok': True, 'tables': ['pool_topics', 'my_views'], 'day': today()})


# ---------------------------------------------------------------- 抽素材
def _sample_rows(c, table, k, cols, where='1=1'):
    """按 rowid 随机抽，避开全表 RANDOM() 扫描（book_chunks 有 24 万行）"""
    row = c.execute('select min(rowid), max(rowid) from %s' % table).fetchone()
    if not row or row[1] is None:
        return []
    lo, hi = row[0], row[1]
    got, tries = [], 0
    while len(got) < k and tries < k * 8:
        tries += 1
        x = random.randint(lo, hi)
        sql = 'select %s from %s where rowid >= ? and %s limit 1' % (cols, table, where)
        r = c.execute(sql, (x,)).fetchone()
        if r:
            got.append(r)
    return got


def _board_posts(c, board, k):
    """按分类板块抽稿库素材（posts 只有 1700 行，RANDOM() 可接受）"""
    sql = ('select p.id, p.author, p.kind, substr(p.text,1,700) as text'
           ' from post_labels l join posts p on p.id = l.post_id'
           ' where l.topic = ? and p.hidden = 0 and p.text is not null and length(p.text) > 120'
           ' order by random() limit ?')
    return c.execute(sql, (board, k)).fetchall()


def _board_chunks(c, board, k):
    """按板块抽书：先随机挑该板块的书，再从书里随机挑一段正文（避开 24 万行全表扫描）"""
    bids = [r[0] for r in c.execute('select distinct book_id from book_labels where topic = ?', (board,))]
    random.shuffle(bids)
    got = []
    for bid in bids:
        if len(got) >= k:
            break
        r = c.execute(
            'select id, book_id, substr(content,1,900) as content from book_chunks'
            ' where book_id = ? and length(content) > 600'
            ' and content not like \'%ISBN%\' and content not like \'%目录%\''
            ' order by random() limit 1', (bid,)).fetchone()
        if r:
            got.append(r)
    return got


def cmd_pick(a):
    c = conn()
    n = int(a.n or 24)
    board = (a.board or '').strip()
    nb = max(2, n // 3)          # 书占 1/3，稿占 2/3
    np_ = n - nb
    out = []

    posts = _board_posts(c, board, np_) if board else _sample_rows(
        c, 'posts', np_,
        'id, author, kind, substr(text,1,700) as text',
        "hidden=0 and text is not null and length(text)>120")
    for r in posts:
        t = (r['text'] or '').strip()
        if not t:
            continue
        out.append({
            'kind': 'post', 'ref': str(r['id']),
            'title': (r['author'] or '') + ' · ' + (r['kind'] or ''),
            'text': t,
        })

    chunks = _board_chunks(c, board, nb) if board else _sample_rows(
        c, 'book_chunks', nb,
        'id, book_id, substr(content,1,900) as content, heading',
        "content is not null and length(content)>600"
        " and content not like '%ISBN%' and content not like '%目录%'"
        " and content not like '%版权%'")
    seen_books = set()
    for r in chunks:
        bid = r['book_id']
        if bid in seen_books:
            continue
        txt = (r['content'] or '').strip()
        # 正文密度太低（封面/版权页/目录）就丢掉，宁可少给几条
        cjk = sum(1 for ch in txt if '\u4e00' <= ch <= '\u9fff')
        if len(txt) < 400 or cjk / max(1, len(txt)) < 0.55:
            continue
        seen_books.add(bid)
        b = c.execute('select title, author from books where id=?', (bid,)).fetchone()
        title = (b['title'] if b else '') or ''
        if not title:
            continue
        out.append({'kind': 'book', 'ref': str(bid), 'title': title, 'text': txt})

    c.close()
    random.shuffle(out)
    emit({'ok': True, 'board': board, 'n': len(out), 'items': out[:n]})


# ---------------------------------------------------------------- 选题
def cmd_list(a):
    c = conn()
    sql = 'select * from pool_topics where 1=1'
    args = []
    if a.day:
        sql += ' and day=?'
        args.append(a.day)
    if a.status:
        sql += ' and status=?'
        args.append(a.status)
    if getattr(a, 'board', None):
        sql += ' and board=?'
        args.append(a.board)
    sql += ' order by score desc, created_at desc limit ?'
    args.append(int(a.limit or 60))
    rows = []
    for r in c.execute(sql, args):
        d = dict(r)
        try:
            d['dims'] = json.loads(d['dims'] or '{}')
        except Exception:
            d['dims'] = {}
        rows.append(d)
    c.close()
    emit({'ok': True, 'total': len(rows), 'topics': rows})


def cmd_import(a):
    data = read_stdin_json()
    if not isinstance(data, list):
        emit({'ok': False, 'error': 'needs JSON array'})
        return
    c = conn()
    day = today()
    added, skipped = 0, 0
    for it in data:
        title = str(it.get('title') or '').strip()
        if not title:
            skipped += 1
            continue
        dup = c.execute('select id from pool_topics where day=? and title=?', (day, title)).fetchone()
        if dup:
            skipped += 1
            continue
        c.execute(
            'insert into pool_topics (id, day, board, title, angle, hook, source_kind, source_ref,'
            ' source_title, dims, score, level, why, status, created_at)'
            ' values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (rid('t'), day, str(it.get('board') or getattr(a, 'board', '') or ''), title,
             str(it.get('angle') or ''), str(it.get('hook') or ''),
             str(it.get('source_kind') or ''), str(it.get('source_ref') or ''),
             str(it.get('source_title') or ''),
             json.dumps(it.get('dims') or {}, ensure_ascii=False),
             int(it.get('score') or 0), str(it.get('level') or ''),
             str(it.get('why') or ''), 'idea', now()))
        added += 1
    c.commit()
    c.close()
    emit({'ok': True, 'added': added, 'skipped': skipped, 'day': day})


def cmd_setstatus(a):
    c = conn()
    st = a.status
    if st not in ('idea', 'writing', 'published', 'dropped'):
        c.close()
        emit({'ok': False, 'error': 'bad status'})
        return
    if st in ('writing', 'published'):
        c.execute('update pool_topics set status=?, used_at=? where id=?', (st, now(), a.id))
    else:
        c.execute('update pool_topics set status=? where id=?', (st, a.id))
    c.commit()
    n = c.total_changes
    c.close()
    emit({'ok': n > 0, 'updated': n})


def cmd_del(a):
    ids = [x.strip() for x in (a.ids or '').split(',') if x.strip()]
    if not ids:
        emit({'ok': False, 'error': 'no ids'})
        return
    c = conn()
    q = 'delete from pool_topics where id in (%s)' % ','.join('?' * len(ids))
    c.execute(q, ids)
    c.commit()
    n = c.total_changes
    c.close()
    emit({'ok': True, 'removed': n})


# ---------------------------------------------------------------- 单条选题 + 原文出处
def cmd_get(a):
    c = conn()
    r = c.execute('select * from pool_topics where id=?', (a.id,)).fetchone()
    c.close()
    if not r:
        emit({'ok': False, 'error': 'not found'})
        return
    d = dict(r)
    try:
        d['dims'] = json.loads(d['dims'] or '{}')
    except Exception:
        d['dims'] = {}
    try:
        d['draft'] = json.loads(d['extra'] or 'null')
    except Exception:
        d['draft'] = None
    emit({'ok': True, 'topic': d})


def cmd_src(a):
    """取这条选题的原始素材：post 取推文全文；book 取书里几段正文"""
    kind = (a.kind or '').strip()
    ref = (a.ref or '').strip()
    c = conn()
    if kind == 'post':
        r = c.execute('select id, author, kind, date, text from posts where id=?', (ref,)).fetchone()
        c.close()
        if not r:
            emit({'ok': False, 'error': '稿库里找不到这条推文：' + ref})
            return
        emit({'ok': True, 'kind': 'post', 'title': (r['author'] or '') + ' · ' + (r['date'] or ''),
              'author': r['author'] or '', 'date': r['date'] or '', 'text': r['text'] or ''})
        return
    if kind == 'book':
        b = c.execute('select id, title, author from books where id=?', (ref,)).fetchone()
        if not b:
            c.close()
            emit({'ok': False, 'error': '书库里找不到这本：' + ref})
            return
        chunks = c.execute(
            'select heading, content from book_chunks where book_id=? and length(content)>500'
            ' order by random() limit 3', (ref,)).fetchall()
        c.close()
        parts = []
        for ch in chunks:
            h = (ch['heading'] or '').strip()
            parts.append((('【' + h + '】\n') if h else '') + (ch['content'] or '').strip())
        emit({'ok': True, 'kind': 'book', 'title': b['title'] or '', 'author': b['author'] or '',
              'date': '', 'text': '\n\n'.join(parts)[:4000]})
        return
    c.close()
    emit({'ok': False, 'error': '不认识的来源类型：' + kind})


def cmd_setdraft(a):
    body = read_stdin_json() or {}
    c = conn()
    c.execute('update pool_topics set extra=? where id=?',
              (json.dumps(body, ensure_ascii=False), a.id))
    c.commit()
    n = c.total_changes
    c.close()
    emit({'ok': n > 0, 'updated': n})


# ---------------------------------------------------------------- 我的观点 / 语料库
def cmd_views_list(a):
    c = conn()
    sql = 'select * from my_views where 1=1'
    args = []
    if a.q:
        sql += ' and (content like ? or title like ?)'
        args += ['%' + a.q + '%', '%' + a.q + '%']
    sql += ' order by created_at desc limit ?'
    args.append(int(a.limit or 50))
    rows = []
    for r in c.execute(sql, args):
        d = dict(r)
        d['content'] = (d['content'] or '')[:400]
        try:
            d['ai_review'] = json.loads(d['ai_review'] or 'null')
        except Exception:
            d['ai_review'] = None
        rows.append(d)
    c.close()
    emit({'ok': True, 'total': len(rows), 'views': rows})


def cmd_views_get(a):
    c = conn()
    r = c.execute('select * from my_views where id=?', (a.id,)).fetchone()
    c.close()
    if not r:
        emit({'ok': False, 'error': 'not found'})
        return
    d = dict(r)
    try:
        d['ai_review'] = json.loads(d['ai_review'] or 'null')
    except Exception:
        d['ai_review'] = None
    emit({'ok': True, 'view': d})


def cmd_views_save(a):
    body = read_stdin_json() or {}
    content = str(body.get('content') or '')
    if not content.strip():
        emit({'ok': False, 'error': 'empty content'})
        return
    c = conn()
    vid = str(body.get('id') or '').strip()
    t = now()
    if vid:
        c.execute('update my_views set title=?, content=?, chars=?, tags=?, updated_at=? where id=?',
                  (str(body.get('title') or ''), content, len(content),
                   str(body.get('tags') or ''), t, vid))
        c.commit()
        c.close()
        emit({'ok': True, 'id': vid, 'updated': True})
        return
    vid = rid('v')
    c.execute(
        'insert into my_views (id, kind, topic_id, title, content, chars, ai_review, status,'
        ' tags, created_at, updated_at) values (?,?,?,?,?,?,?,?,?,?,?)',
        (vid, str(body.get('kind') or 'free'), str(body.get('topicId') or ''),
         str(body.get('title') or ''), content, len(content), '', 'saved',
         str(body.get('tags') or ''), t, t))
    c.commit()
    c.close()
    emit({'ok': True, 'id': vid, 'created': True, 'chars': len(content)})


def cmd_views_review(a):
    body = read_stdin_json() or {}
    c = conn()
    c.execute('update my_views set ai_review=?, status=?, updated_at=? where id=?',
              (json.dumps(body, ensure_ascii=False), 'reviewed', now(), a.id))
    c.commit()
    n = c.total_changes
    c.close()
    emit({'ok': n > 0, 'updated': n})


def cmd_views_del(a):
    ids = [x.strip() for x in (a.ids or '').split(',') if x.strip()]
    if not ids:
        emit({'ok': False, 'error': 'no ids'})
        return
    c = conn()
    q = 'delete from my_views where id in (%s)' % ','.join('?' * len(ids))
    c.execute(q, ids)
    c.commit()
    n = c.total_changes
    c.close()
    emit({'ok': True, 'removed': n})


def cmd_boards(a):
    """今日各板块出了几条 + 全库总数，界面用它决定哪个板块要补"""
    c = conn()
    d = today()
    rows = c.execute(
        'select board, count(*) n, max(created_at) last_at from pool_topics where day=?'
        ' group by board order by n desc', (d,)).fetchall()
    boards = [{'board': r['board'] or '未分板块', 'n': r['n'], 'last_at': r['last_at']} for r in rows]
    total = c.execute('select count(*) from pool_topics where day=?', (d,)).fetchone()[0]
    c.close()
    emit({'ok': True, 'day': d, 'total': total, 'boards': boards})


def cmd_stats(a):
    c = conn()
    out = {'ok': True, 'day': today()}
    for t in ('pool_topics', 'my_views'):
        try:
            out[t] = c.execute('select count(*) from %s' % t).fetchone()[0]
        except Exception:
            out[t] = None
    try:
        out['today'] = c.execute('select count(*) from pool_topics where day=?', (today(),)).fetchone()[0]
    except Exception:
        out['today'] = 0
    try:
        out['byStatus'] = {r[0]: r[1] for r in c.execute('select status, count(*) from pool_topics group by status')}
    except Exception:
        out['byStatus'] = {}
    c.close()
    emit(out)


# ---------------- 我的灵感 ----------------

def cmd_ideas_list(a):
    c = conn()
    lim = int(a.limit or 100)
    rows = c.execute(
        'select id, source, content, note, tags, status, created_at, used_at '
        'from ideas order by created_at desc limit ?', (lim,)).fetchall()
    c.close()
    out = [{'id': r[0], 'source': r[1], 'content': r[2], 'note': r[3], 'tags': r[4],
            'status': r[5], 'created_at': r[6], 'used_at': r[7]} for r in rows]
    stale = 0
    try:
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')
        stale = len([x for x in out if x['status'] == 'new' and (x['created_at'] or '') < cutoff])
    except Exception:
        pass
    emit({'ok': True, 'count': len(out), 'stale': stale, 'ideas': out})


def cmd_ideas_add(a):
    body = read_stdin_json() or {}
    content = str(body.get('content') or a.content or '').strip()
    if not content:
        emit({'ok': False, 'error': 'empty content'})
        return
    c = conn()
    iid = rid('idea')
    c.execute('insert into ideas (id, source, content, note, tags, status, created_at) values (?,?,?,?,?,?,?)',
              (iid, str(body.get('source') or 'manual'), content, str(body.get('note') or ''),
               str(body.get('tags') or ''), 'new', now()))
    c.commit()
    c.close()
    emit({'ok': True, 'id': iid, 'chars': len(content)})


def cmd_ideas_del(a):
    ids = [x.strip() for x in str(a.ids or '').split(',') if x.strip()]
    if not ids:
        emit({'ok': False, 'error': 'no ids'})
        return
    c = conn()
    c.executemany('delete from ideas where id=?', [(i,) for i in ids])
    c.commit()
    n = c.total_changes
    c.close()
    emit({'ok': True, 'deleted': n})


def cmd_ideas_promote(a):
    if not a.id:
        emit({'ok': False, 'error': 'no id'})
        return
    c = conn()
    row = c.execute('select id, content, tags from ideas where id=?', (a.id,)).fetchone()
    if not row:
        c.close()
        emit({'ok': False, 'error': 'idea not found'})
        return
    body = read_stdin_json() or {}
    content = str(body.get('content') or row[1])
    title = str(body.get('title') or content[:40])
    t = now()
    vid = rid('v')
    c.execute('insert into my_views (id, kind, topic_id, title, content, chars, ai_review, status, tags, created_at, updated_at)'
              ' values (?,?,?,?,?,?,?,?,?,?,?)',
              (vid, 'idea', '', title, content, len(content), '', 'saved',
               (row[2] or '') + ',来自灵感', t, t))
    c.execute('update ideas set status=?, used_at=? where id=?', ('promoted', t, a.id))
    c.commit()
    c.close()
    emit({'ok': True, 'view_id': vid, 'idea_id': a.id})


# ---------------- 每日对撞 ----------------

def _ensure_clash_seen(c):
    c.execute('CREATE TABLE IF NOT EXISTS clash_seen ('
              'atom_id TEXT PRIMARY KEY, day TEXT NOT NULL, created_at TEXT NOT NULL)')


def cmd_clash_today(a):
    n = max(1, min(5, int(a.n or 2)))
    c = conn()
    _ensure_clash_seen(c)
    try:
        recent = [r[0] for r in c.execute(
            "select atom_id from clash_seen where day >= date('now','-30 day')")]
    except Exception:
        recent = []
    q = ("select id, author, knowledge, topics, confidence, original from atoms "
         "where (hidden is null or hidden=0) and confidence in ('high','medium') "
         "and length(knowledge) between 16 and 180")
    rows = c.execute(q).fetchall()
    pool = [r for r in rows if r[0] not in recent]
    if len(pool) < n:
        pool = rows
    picked = random.sample(pool, min(n, len(pool))) if pool else []
    day = datetime.datetime.now().strftime('%Y-%m-%d')
    t = now()
    out = []
    for r in picked:
        c.execute('insert or ignore into clash_seen (atom_id, day, created_at) values (?,?,?)',
                  (r[0], day, t))
        out.append({'atom_id': r[0], 'author': r[1], 'claim': r[2], 'topics': r[3],
                    'confidence': r[4], 'original': (r[5] or '')[:600]})
    c.commit()
    answered = c.execute(
        "select count(*) from my_views where kind='clash' and date(created_at)=date('now')").fetchone()[0]
    c.close()
    emit({'ok': True, 'day': day, 'items': out, 'answered_today': answered})


def cmd_clash_answer(a):
    atom = str(a.ref or '').strip()
    if not atom:
        emit({'ok': False, 'error': 'missing atom id'})
        return
    verdict = str(a.kind or 'unsure')
    if verdict not in ('agree', 'disagree', 'unsure'):
        verdict = 'unsure'
    why = str(a.content or '').strip()
    if not why:
        emit({'ok': False, 'error': '必须写点什么才能存——没有输出，这条知识就不是你的'})
        return
    c = conn()
    r = c.execute('select author, knowledge from atoms where id=?', (atom,)).fetchone()
    src = (r[1] if r else '').strip().rstrip('\\\\').strip()
    who = (r[0] if r else '')
    label = {'agree': '同意', 'disagree': '不同意', 'unsure': '说不清'}[verdict]
    title = (label + '「' + src[:24] + '」') if src else (label + '一条观点')
    content = '【我的态度】' + label + '\n【对方观点】' + src + '\n【作者】' + who + '\n'
    if why:
        content += '【我的理由/延伸】' + why
    vid = rid('v')
    c.execute('insert into my_views (id, kind, topic_id, title, content, chars, ai_review, status, tags, created_at, updated_at)'
              ' values (?,?,?,?,?,?,?,?,?,?,?)',
              (vid, 'clash', atom, title, content, len(content), '',
               'saved',
               ','.join(['对撞', verdict, atom]), now(), now()))
    c.commit()
    c.close()
    emit({'ok': True, 'view_id': vid, 'verdict': verdict, 'need_why': not why})


def cmd_clash_pending(a):
    c = conn()
    rows = c.execute("select id, title, content, tags, created_at from my_views "
                     "where kind='clash' and status='pending_why' "
                     "order by created_at desc limit 50").fetchall()
    c.close()
    out = [{'id': r[0], 'title': r[1], 'content': r[2], 'tags': r[3], 'created_at': r[4]} for r in rows]
    emit({'ok': True, 'count': len(out), 'pending': out})


def cmd_clash_list(a):
    """观点库：平铺所有还没表过态的原子。不分类、不分组，就是一条流。"""
    lim = max(1, min(500, int(a.limit or 60)))
    where = ["coalesce(a.hidden,0)=0"]
    args = []
    if a.kind:
        where.append("a.type = ?")
        args.append(a.kind)
    if a.q:
        where.append("a.knowledge like ?")
        args.append("%" + a.q + "%")
    sql = (
        "select a.id, a.author, a.knowledge, a.type, a.confidence, a.original, a.url "
        "from atoms a where " + " and ".join(where) +
        " and a.id not in (select coalesce(topic_id,'') from my_views where kind='clash') "
        "order by random() limit ?"
    )
    args.append(lim)
    c = conn()
    rows = c.execute(sql, args).fetchall()
    left = c.execute(
        "select count(*) from atoms a where coalesce(a.hidden,0)=0 "
        "and a.id not in (select coalesce(topic_id,'') from my_views where kind='clash')"
    ).fetchone()[0]
    done = c.execute("select count(*) from my_views where kind='clash'").fetchone()[0]
    c.close()
    out = [{'id': r[0], 'author': r[1], 'claim': r[2], 'type': r[3],
            'confidence': r[4], 'original': (r[5] or '')[:400], 'url': r[6]} for r in rows]
    emit({'ok': True, 'left': left, 'done': done, 'count': len(out), 'items': out})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('--n', default=None)
    ap.add_argument('--day', default=None)
    ap.add_argument('--status', default=None)
    ap.add_argument('--limit', default=None)
    ap.add_argument('--id', default=None)
    ap.add_argument('--ids', default=None)
    ap.add_argument('--q', default=None)
    ap.add_argument('--board', default=None)
    ap.add_argument('--min', default=None)
    ap.add_argument('--kind', default=None)
    ap.add_argument('--ref', default=None)
    ap.add_argument('--content', default=None)
    ap.add_argument('--why', default=None)
    a = ap.parse_args()
    fn = {
        'init': cmd_init, 'pick': cmd_pick, 'list': cmd_list, 'import': cmd_import,
        'boards': cmd_boards, 'get': cmd_get, 'src': cmd_src, 'setdraft': cmd_setdraft,
        'setstatus': cmd_setstatus, 'del': cmd_del,
        'views_list': cmd_views_list, 'views_get': cmd_views_get,
        'views_save': cmd_views_save, 'views_review': cmd_views_review,
        'views_del': cmd_views_del, 'stats': cmd_stats, 'boards': cmd_boards,
        'ideas_list': cmd_ideas_list, 'ideas_add': cmd_ideas_add,
        'ideas_del': cmd_ideas_del, 'ideas_promote': cmd_ideas_promote,
        'clash_today': cmd_clash_today, 'clash_answer': cmd_clash_answer, 'clash_list': cmd_clash_list,
        'clash_pending': cmd_clash_pending,
    }.get(a.cmd)
    if not fn:
        emit({'ok': False, 'error': 'unknown cmd ' + a.cmd})
        return
    try:
        fn(a)
    except Exception as e:
        emit({'ok': False, 'error': '%s: %s' % (type(e).__name__, e)})


if __name__ == '__main__':
    main()
