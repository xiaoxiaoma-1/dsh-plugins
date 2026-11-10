# -*- coding: utf-8 -*-
"""自媒体工作台 · 库查询（给 DSH 宿主插件调用，输出 JSON 到 stdout）
用法：
  wbquery.py summary
  wbquery.py posts [author] [limit]
  wbquery.py atoms [type] [limit]
  wbquery.py post <id>
"""
import sys, json, sqlite3

DB = r'E:\desktop\media\workbench.db'


def q(sql, args=()):
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        return cur.execute(sql, args).fetchall()
    finally:
        con.close()


def summary():
    posts = q('select count(*) from posts where coalesce(hidden,0)=0')[0][0]
    atoms = q('select count(*) from atoms where coalesce(hidden,0)=0')[0][0]
    hidden_posts = q('select count(*) from posts where coalesce(hidden,0)=1')[0][0]
    hidden_atoms = q('select count(*) from atoms where coalesce(hidden,0)=1')[0][0]
    fuzz_atoms = q("select count(*) from atoms where coalesce(hidden,0)=0 and coalesce(flag,'')='fuzz'")[0][0]
    keep_atoms = q("select count(*) from atoms where coalesce(hidden,0)=0 and coalesce(flag,'')=''")[0][0]
    authors = q('''
        select author, count(*) n, min(date), max(date)
        from posts where coalesce(hidden,0)=0 group by author order by n desc limit 20
    ''')
    types = q('select type, count(*) n from atoms where coalesce(hidden,0)=0 group by type order by n desc')

    # ===== 内容库总账（2026-11-07 新增）：四类来源数量 + 最近新增 + 分类分布 =====
    def _cnt(sql, args=()):
        try:
            return q(sql, args)[0][0] or 0
        except Exception:
            return 0

    tweet = _cnt("select count(*) from posts where coalesce(hidden,0)=0 and kind in ('主贴','引用','文章')")
    douyin = _cnt("select count(*) from posts where coalesce(hidden,0)=0 and kind='douyin'")
    # 直播按「场」算（posts 表 kind='live' 每场一条），段数另存
    live_shows = _cnt("select count(*) from posts where kind='live'")
    live_seg = _cnt("select count(*) from live_segments")
    book = _cnt("select count(*) from books")
    book_chars = _cnt("select sum(length(content)) from book_chunks")
    live_chars = _cnt("select sum(length(text)) from live_segments")

    # 最近 7 天新增（每个来源分别算，绝不共用同一个数）
    def _recent(sql):
        try:
            return q(sql)[0][0] or 0
        except Exception:
            return 0

    recent_tweet = _recent("select count(*) from posts where created_at >= date('now','-7 day') and kind in ('主贴','引用','文章')")
    recent_douyin = _recent("select count(*) from posts where created_at >= date('now','-7 day') and kind='douyin'")
    recent_live = _recent("select count(*) from posts where created_at >= date('now','-7 day') and kind='live'")
    recent_books = 0

    # 三层分类分布：书 + 文案合并
    topic_ct = {}
    for sql in ("select topics from book_classify", "select topics from post_classify"):
        try:
            for (ts,) in q(sql):
                for t in (ts or '').split(','):
                    if t:
                        topic_ct[t] = topic_ct.get(t, 0) + 1
        except Exception:
            pass
    tag_ct = {}
    for sql in ("select tags from book_classify", "select tags from post_classify"):
        try:
            for (ts,) in q(sql):
                for t in (ts or '').split(','):
                    if t:
                        tag_ct[t] = tag_ct.get(t, 0) + 1
        except Exception:
            pass

    return {
        'ok': True,
        'posts': posts,
        'atoms': atoms,
        'hiddenPosts': hidden_posts,
        'hiddenAtoms': hidden_atoms,
        'fuzzAtoms': fuzz_atoms,
        'keepAtoms': keep_atoms,
        'authors': [{'name': a or '未知', 'posts': n, 'first': f, 'last': l} for a, n, f, l in authors],
        'atomTypes': [{'type': t or '未分类', 'n': n} for t, n in types],
        # 内容库总账
        'bySource': [
            {'key': '推文', 'n': tweet, 'chars': sum(
                (x[0] or 0) for x in q("select length(coalesce(text,'')) from posts where coalesce(hidden,0)=0 and kind in ('主贴','引用','文章')"))},
            {'key': '抖音文案', 'n': douyin, 'chars': sum(
                (x[0] or 0) for x in q("select length(coalesce(text,'')) from posts where coalesce(hidden,0)=0 and kind='douyin'"))},
            {'key': '直播', 'n': live_shows, 'unit': '场', 'chars': live_chars, 'segments': live_seg},
            {'key': '书', 'n': book, 'chars': book_chars},
        ],
        'recent': {'推文': recent_tweet, '抖音文案': recent_douyin, '直播': recent_live, '书': recent_books},
        'topics': sorted([{'name': k, 'n': v} for k, v in topic_ct.items()], key=lambda x: -x['n']),
        'tagTop': sorted([{'name': k, 'n': v} for k, v in tag_ct.items()], key=lambda x: -x['n'])[:30],
    }


def _topic_map():
    """url -> 这篇稿子的主话题（取该 url 下所有原子 topics[0] 里出现最多的那个）"""
    rows = q("select url, topics from atoms where topics is not null and topics != '[]'")
    agg = {}
    for url, topics in rows:
        if not url:
            continue
        try:
            arr = json.loads(topics)
        except Exception:
            continue
        if not arr:
            continue
        d = agg.setdefault(url, {})
        d[arr[0]] = d.get(arr[0], 0) + 1
    return {u: max(d, key=d.get) for u, d in agg.items()}


def posts(author=None, limit=60, topic=None, order=None, source=None):
    tmap = _topic_map()
    cond = ['coalesce(hidden,0)=0']
    args = []
    if author:
        cond.append('author=?')
        args.append(author)
    if source:
        cond.append('kind=?')
        args.append(source)
    where = 'where ' + ' and '.join(cond)
    order_sql = 'created_at desc' if order == 'created' else 'date desc'
    rows = q('''select id, author, date, kind, substr(text,1,400), url, topic_override,
                       (select count(*) from atoms a where a.url=posts.url and coalesce(a.hidden,0)=0)
                from posts %s order by %s''' % (where, order_sql), tuple(args))
    out = []
    counter = {}
    for r in rows:
        if r[3] == 'book':
            t = '书籍'
        else:
            t = r[6] or tmap.get(r[5]) or '未分类'
        counter[t] = counter.get(t, 0) + 1
        if topic and t != topic:
            continue
        out.append({'id': r[0], 'author': r[1], 'date': r[2], 'kind': r[3],
                    'text': r[4], 'url': r[5], 'topic': t, 'atomCount': r[7] or 0})
    total = len(out)
    out = out[:limit]
    topics = [{'name': k, 'n': v} for k, v in sorted(counter.items(), key=lambda x: -x[1])]
    return {'ok': True, 'list': out, 'topics': topics, 'filtered': total}


def split_items(board=None, limit=80, offset=0, kw=None):
    """文案拆解五板块（干货/案例/金句/避坑/问答）"""
    cond = []
    args = []
    if board:
        cond.append('board=?')
        args.append(board)
    if kw:
        cond.append('text like ?')
        args.append('%' + kw + '%')
    where = ('where ' + ' and '.join(cond)) if cond else ''
    total = q('select count(*) from split_items ' + where, tuple(args))[0][0]
    rows = q('''select id, post_id, board, text, note, date, source
                from split_items %s order by date desc limit ? offset ?''' % where,
             tuple(args) + (int(limit), int(offset)))
    dist = q("select board, count(*) from split_items group by board order by 2 desc")
    return {'ok': True, 'total': total, 'offset': int(offset),
            'boards': [{'name': a, 'n': b} for a, b in dist],
            'list': [{'id': r[0], 'postId': r[1], 'board': r[2], 'text': r[3],
                      'note': r[4], 'date': r[5], 'source': r[6]} for r in rows]}


def hooks(style=None, limit=60, offset=0, kw=None):
    """钩子库：每篇稿的开头句，按打法检索"""
    cond = ['junk=0']
    args = []
    if style:
        cond.append('style=?')
        args.append(style)
    if kw:
        cond.append('text like ?')
        args.append('%' + kw + '%')
    where = 'where ' + ' and '.join(cond)
    total = q('select count(*) from hooks ' + where, tuple(args))[0][0]
    rows = q('''select id, text, kind_post, date, style, post_id, source
                from hooks %s order by date desc limit ? offset ?''' % where,
             tuple(args) + (int(limit), int(offset)))
    dist = q("""select coalesce(style,'其他'), count(*) from hooks
                where junk=0 group by style order by 2 desc""")
    return {'ok': True, 'total': total, 'offset': int(offset),
            'styles': [{'name': a, 'n': b} for a, b in dist],
            'list': [{'id': r[0], 'text': r[1], 'kind': r[2], 'date': r[3],
                      'style': r[4], 'postId': r[5], 'source': r[6]} for r in rows]}


def atoms(atype=None, limit=80, offset=0, view=None, kw=None):
    """view: all(默认，未删) / keep(未标记) / fuzz(待定) / trash(已删)"""
    cond = []
    args = []
    if view == 'trash':
        cond.append('coalesce(hidden,0)=1')
    else:
        cond.append('coalesce(hidden,0)=0')
        if view == 'keep':
            cond.append("coalesce(flag,'')=''")
        elif view == 'fuzz':
            cond.append("coalesce(flag,'')='fuzz'")
    if atype:
        cond.append('type=?')
        args.append(atype)
    if kw:
        cond.append('(knowledge like ? or original like ?)')
        args.append('%' + kw + '%')
        args.append('%' + kw + '%')
    where = 'where ' + ' and '.join(cond)
    total = q('select count(*) from atoms ' + where, tuple(args))[0][0]
    rows = q('''select id, type, author, knowledge, original, url, date, confidence, flag, coalesce(hidden,0),
                       (select p.id from posts p where p.url=atoms.url and coalesce(p.hidden,0)=0 limit 1)
                from atoms %s order by date desc, id desc limit ? offset ?''' % where,
             tuple(args) + (int(limit), int(offset)))
    return {'ok': True, 'total': total, 'offset': int(offset), 'list': [
        {'id': r[0], 'type': r[1], 'author': r[2], 'knowledge': r[3],
         'original': r[4], 'url': r[5], 'date': r[6], 'confidence': r[7],
         'flag': r[8], 'hidden': r[9], 'postId': r[10]}
        for r in rows
    ]}


def post_atoms(pid, limit=100):
    """某篇稿子拆出的原子"""
    if not pid:
        return {'ok': False, 'error': 'missing id'}
    rows = q('''select a.id, a.type, a.knowledge, a.original, a.date, a.flag, coalesce(a.hidden,0)
                from atoms a join posts p on p.url=a.url
                where p.id=? and coalesce(a.hidden,0)=0
                order by a.date desc limit ?''', (pid, int(limit)))
    total = q('''select count(*) from atoms a join posts p on p.url=a.url
                 where p.id=? and coalesce(a.hidden,0)=0''', (pid,))[0][0]
    return {'ok': True, 'total': total, 'list': [
        {'id': r[0], 'type': r[1], 'knowledge': r[2], 'original': r[3],
         'date': r[4], 'flag': r[5], 'hidden': r[6]}
        for r in rows
    ]}


def del_posts(ids):
    """彻底删除稿子（连带它的原子与来源记录），不可恢复"""
    arr = [x.strip() for x in (ids or '').split(',') if x.strip()]
    if not arr:
        return {'ok': False, 'error': 'empty ids'}
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        ph = ','.join(['?'] * len(arr))
        urls = [r[0] for r in cur.execute(
            'select url from posts where id in (' + ph + ') and url is not null and url != \'\'', tuple(arr))]
        npost = cur.execute('delete from posts where id in (' + ph + ')', tuple(arr)).rowcount
        natom = 0
        if urls:
            uph = ','.join(['?'] * len(urls))
            natom = cur.execute('delete from atoms where url in (' + uph + ')', tuple(urls)).rowcount
        nsrc = cur.execute('delete from post_sources where post_id in (' + ph + ')', tuple(arr)).rowcount
        con.commit()
    finally:
        con.close()
    return {'ok': True, 'deletedPosts': npost, 'deletedAtoms': natom, 'deletedSources': nsrc}


def set_post_hidden(ids, hidden):
    """批量隐藏/恢复稿子"""
    arr = [x.strip() for x in (ids or '').split(',') if x.strip()]
    if not arr:
        return {'ok': False, 'error': 'empty ids'}
    ph = ','.join(['?'] * len(arr))
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute('update posts set hidden=? where id in (' + ph + ')', (int(hidden),) + tuple(arr))
        con.commit()
        n = cur.rowcount
    finally:
        con.close()
    return {'ok': True, 'updated': n, 'hidden': int(hidden)}


def set_hidden(ids, hidden):
    """批量隐藏/恢复原子，ids 用逗号分隔"""
    arr = [x.strip() for x in (ids or '').split(',') if x.strip()]
    if not arr:
        return {'ok': False, 'error': 'empty ids'}
    ph = ','.join(['?'] * len(arr))
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute('update atoms set hidden=? where id in (' + ph + ')', (int(hidden),) + tuple(arr))
        con.commit()
        n = cur.rowcount
    finally:
        con.close()
    return {'ok': True, 'updated': n, 'hidden': int(hidden)}


def set_flag(ids, flag):
    arr = [x.strip() for x in (ids or '').split(',') if x.strip()]
    if not arr:
        return {'ok': False, 'error': 'empty ids'}
    ph = ','.join(['?'] * len(arr))
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute('update atoms set flag=? where id in (' + ph + ')', (flag or None,) + tuple(arr))
        con.commit()
        n = cur.rowcount
    finally:
        con.close()
    return {'ok': True, 'updated': n, 'flag': flag}


def post(pid):
    """单篇逐字稿全文（采集台「看逐字稿」用）"""
    rows = q('select id, author, date, kind, text, url, created_at from posts where id=?', (pid,))
    if not rows:
        return {'ok': False, 'error': 'not found: ' + str(pid)}
    r = rows[0]
    src = q('select platform, title, vid, duration, audio_path from post_sources where post_id=?', (pid,))
    return {
        'ok': True,
        'id': r[0], 'author': r[1], 'date': r[2], 'kind': r[3],
        'text': r[4], 'url': r[5], 'created_at': r[6],
        'title': (src[0][1] if src else None),
        'platform': (src[0][0] if src else None),
        'duration': (src[0][3] if src else None),
        'chars': len(r[4] or ''),
    }


def search(kw, limit=8):
    """按关键词在原子库里做朴素检索（给分身/圆桌用）"""
    import re as _re
    words = [w for w in _re.split(r'[\s,，、。？?！!；;：:]+', kw or '') if len(w) >= 2][:6]
    if not words:
        return {'ok': True, 'list': []}
    cond = ' or '.join(['knowledge like ?'] * len(words))
    args = tuple('%' + w + '%' for w in words) + (int(limit),)
    rows = q('select id, type, author, knowledge, original, url, topics, confidence from atoms '
             'where coalesce(hidden,0)=0 and (' + cond + ') order by date desc limit ?', args)
    return {'ok': True, 'list': [
        {'id': r[0], 'type': r[1], 'author': r[2], 'knowledge': r[3],
         'original': r[4], 'url': r[5], 'topics': r[6], 'confidence': r[7]}
        for r in rows
    ]}


def bytopic(topic, limit=40):
    """按话题取原子（第一个 topic 命中）"""
    rows = q("select id, type, author, knowledge, original, url, topics, confidence from atoms "
             "where coalesce(hidden,0)=0 and topics like ? order by date desc limit ?",
             ('%"' + (topic or "") + '"%', int(limit),))
    return {'ok': True, 'list': [
        {'id': r[0], 'type': r[1], 'author': r[2], 'knowledge': r[3],
         'original': r[4], 'url': r[5], 'topics': r[6], 'confidence': r[7]}
        for r in rows
    ]}


def topics_dist():
    """原子按主话题分布"""
    import collections
    c = collections.Counter()
    for (t,) in q("select topics from atoms where coalesce(hidden,0)=0 and topics is not null and topics != '[]'"):
        try:
            arr = json.loads(t)
            if arr:
                c[arr[0]] += 1
        except Exception:
            pass
    total = q("select count(*) from atoms where coalesce(hidden,0)=0")[0][0]
    return {'ok': True, 'total': total, 'topics': [{'name': k, 'n': v} for k, v in c.most_common()]}


def fitness_init():
    """初始化健身记录表（如果不存在则创建）"""
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS workout_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,          -- 日期，格式：'YYYY-MM-DD'
                body_part TEXT NOT NULL,     -- 练的部位
                duration_minutes INTEGER NOT NULL, -- 时长分钟
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_workout_date ON workout_logs(date)')
        con.commit()
    finally:
        con.close()
    return {'ok': True, 'message': 'workout_logs table ready'}


def fitness_summary():
    """获取今日健身摘要"""
    fitness_init()  # 确保表存在
    today = q("SELECT date('now', 'localtime')")[0][0]
    rows = q("SELECT body_part, SUM(duration_minutes) FROM workout_logs WHERE date=? GROUP BY body_part", (today,))
    logs = [{'body_part': r[0], 'total_minutes': r[1]} for r in rows]
    total_minutes = sum(r[1] for r in rows)
    return {
        'ok': True,
        'today': today,
        'logs': logs,
        'total_minutes': total_minutes,
        'count': len(rows)
    }


def fitness_log(date=None, body_part=None, duration_minutes=None):
    """记录健身"""
    fitness_init()  # 确保表存在
    # date 是可选参数，如果为空字符串或 None，则使用今天
    if not date or date == '""' or date == '' or date == 'None':
        date = q("SELECT date('now', 'localtime')")[0][0]
    # 检查 body_part 和 duration_minutes
    if (not body_part or body_part == '""' or body_part == '' or body_part == 'None' or 
        not duration_minutes or duration_minutes == '""' or duration_minutes == '' or duration_minutes == 'None'):
        return {'ok': False, 'error': '缺少部位或时长'}
    
    try:
        duration = int(duration_minutes)
        if duration <= 0:
            return {'ok': False, 'error': '时长必须为正整数'}
    except ValueError:
        return {'ok': False, 'error': '时长必须为整数'}
    
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO workout_logs (date, body_part, duration_minutes) VALUES (?, ?, ?)",
            (date, body_part.strip(), duration)
        )
        con.commit()
        return {'ok': True, 'id': cur.lastrowid, 'date': date, 'body_part': body_part, 'duration_minutes': duration}
    finally:
        con.close()


def fitness_list(limit=7):
    """获取最近健身记录"""
    fitness_init()  # 确保表存在
    rows = q("""
        SELECT id, date, body_part, duration_minutes, created_at 
        FROM workout_logs 
        ORDER BY date DESC, created_at DESC 
        LIMIT ?
    """, (limit,))
    return {
        'ok': True,
        'logs': [
            {
                'id': r[0],
                'date': r[1],
                'body_part': r[2],
                'duration_minutes': r[3],
                'created_at': r[4]
            }
            for r in rows
        ]
    }


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'summary'
    try:
        if cmd == 'summary':
            out = summary()
        elif cmd == 'posts':
            a = sys.argv[2] if len(sys.argv) > 2 else None
            n = int(sys.argv[3]) if len(sys.argv) > 3 else 60
            tp = sys.argv[4] if len(sys.argv) > 4 else None
            od = sys.argv[5] if len(sys.argv) > 5 else None
            sc = sys.argv[6] if len(sys.argv) > 6 else None
            out = posts(a or None, n, tp or None, od or None, sc or None)
        elif cmd == 'topics':
            out = topics_dist()
        elif cmd == 'bytopic':
            tp = sys.argv[2] if len(sys.argv) > 2 else ''
            n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
            out = bytopic(tp, n)
        elif cmd == 'search':
            kw = sys.argv[2] if len(sys.argv) > 2 else ''
            n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
            out = search(kw, n)
        elif cmd == 'post':
            pid = sys.argv[2] if len(sys.argv) > 2 else ''
            out = post(pid)
        elif cmd == 'atoms':
            t = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
            n = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else 80
            off = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else 0
            view = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else None
            kw = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] else None
            out = atoms(t, n, off, view, kw)
        elif cmd == 'hooks':
            st = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
            n = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else 60
            off = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else 0
            kw = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else None
            out = hooks(st, n, off, kw)
        elif cmd == 'split':
            b = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
            n = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else 80
            off = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else 0
            kw = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else None
            out = split_items(b, n, off, kw)
        elif cmd == 'postatoms':
            out = post_atoms(sys.argv[2] if len(sys.argv) > 2 else '', int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else 100)
        elif cmd == 'hide':
            out = set_hidden(sys.argv[2] if len(sys.argv) > 2 else '', sys.argv[3] if len(sys.argv) > 3 else 1)
        elif cmd == 'hidepost':
            out = set_post_hidden(sys.argv[2] if len(sys.argv) > 2 else '', sys.argv[3] if len(sys.argv) > 3 else 1)
        elif cmd == 'delpost':
            out = del_posts(sys.argv[2] if len(sys.argv) > 2 else '')
        elif cmd == 'flag':
            out = set_flag(sys.argv[2] if len(sys.argv) > 2 else '', sys.argv[3] if len(sys.argv) > 3 else 'fuzz')
        elif cmd == 'fitness':
            # fitness 命令子命令：summary/log/list/init
            subcmd = sys.argv[2] if len(sys.argv) > 2 else 'summary'
            if subcmd == 'summary':
                out = fitness_summary()
            elif subcmd == 'log':
                # wbquery.py fitness log [date] body_part duration_minutes
                # 可选日期参数，如果没有日期或日期看起来像是数字，则假设没有日期参数
                if len(sys.argv) > 5:
                    # 3个参数：日期、部位、时长
                    date = sys.argv[3]
                    body_part = sys.argv[4]
                    duration = sys.argv[5]
                elif len(sys.argv) > 4:
                    # 2个参数：部位、时长（无日期）
                    date = None
                    body_part = sys.argv[3]
                    duration = sys.argv[4]
                else:
                    date = None
                    body_part = None
                    duration = None
                out = fitness_log(date, body_part, duration)
            elif subcmd == 'list':
                limit = int(sys.argv[3]) if len(sys.argv) > 3 else 7
                out = fitness_list(limit)
            elif subcmd == 'init':
                out = fitness_init()
            else:
                out = {'ok': False, 'error': 'unknown fitness subcommand: ' + subcmd}
        else:
            out = {'ok': False, 'error': 'unknown command: ' + cmd}
    except Exception as e:
        out = {'ok': False, 'error': str(e)}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
