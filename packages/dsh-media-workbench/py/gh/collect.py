# -*- coding: utf-8 -*-
"""GitHub 榜单采集：日/周/月涨星 + 总星 Top100 + 近一年新秀。

数据源：
- https://github.com/trending?since=daily|weekly|monthly  （页面自带「N stars today/week/month」）
- https://api.github.com/search/repositories              （总星 Top100、近一年新建项目）

统一入库 trending.db：
  repos(repo, lang, desc, topics, first_seen, last_seen, intro, intro_at)
  list_items(list, date, rank, repo, stars, gained, lang, desc)
  judged(repo, verdict, at, card_id)
  meta(key, value)

用法：
  python collect.py                 五张榜全跑
  python collect.py --only=daily    只跑其中几张（逗号分隔：daily/weekly/monthly/top100/year）
"""
import json
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'trending.db')
UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36',
    'Accept': 'application/vnd.github+json',
}
TOKEN = os.environ.get('GITHUB_TOKEN', '').strip()
if TOKEN:
    UA['Authorization'] = 'Bearer ' + TOKEN

TRENDING = ['daily', 'weekly', 'monthly']
EMOJI = re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u20E3]+')


def clean_desc(s, limit=300):
    s = EMOJI.sub('', s or '')
    s = re.sub(r'\s+', ' ', s).strip(' .,|-')
    if len(s) > limit:
        s = s[:limit].rstrip() + '…'
    return s


def fetch_page(since):
    req = urllib.request.Request('https://github.com/trending?since=' + since, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', errors='replace')


def parse_trending(html):
    """解析 trending 页。涨星数按页面上的 today / this week / this month 文案取。"""
    items = []
    for block in re.split(r'<article class="Box-row"', html)[1:]:
        h2 = block.split('</h2>')[0]
        cands = re.findall(r'href="/([^/"?]+/[^/"?]+)"', h2)
        repo = ''
        for c in cands:
            if c.split('/')[0].lower() in ('sponsors', 'login', 'topics', 'collections', 'orgs'):
                continue
            repo = c.strip('/')
            break
        if not repo:
            continue
        lang = ''
        ml = re.search(r'itemprop="programmingLanguage">([^<]+)<', block)
        if ml:
            lang = ml.group(1).strip()
        desc = ''
        md = re.search(r'<p class="col-9[^"]*">\s*(.*?)\s*</p>', block, re.S)
        if md:
            desc = re.sub(r'<[^>]+>', '', md.group(1)).strip()
        desc = clean_desc(desc)
        stars = 0
        ms = re.search(r'href="/' + re.escape(repo) + r'/stargazers"[^>]*>(.*?)</a>', block, re.S)
        if ms:
            digits = re.sub(r'<[^>]+>', ' ', ms.group(1))
            mdig = re.search(r'([\d,]{2,})', digits)
            if mdig:
                stars = int(mdig.group(1).replace(',', ''))
        gained = 0
        mt = re.search(r'([\d,]+)\s+stars?\s+(today|this week|this month)', block)
        if mt:
            gained = int(mt.group(1).replace(',', ''))
        items.append({'repo': repo, 'lang': lang, 'desc': desc, 'stars': stars, 'gained': gained})
    return items


def fetch_search(query, per_page=100):
    url = ('https://api.github.com/search/repositories?q=' + urllib.parse.quote(query)
           + '&sort=stars&order=desc&per_page=' + str(per_page))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode('utf-8'))
    items = []
    for it in data.get('items', []):
        items.append({
            'repo': it.get('full_name') or '',
            'lang': it.get('language') or '',
            'desc': clean_desc(it.get('description') or ''),
            'topics': ','.join(it.get('topics') or []),
            'stars': int(it.get('stargazers_count') or 0),
            'gained': 0,
        })
    return [it for it in items if it['repo']]


def ensure_schema(con):
    con.execute('create table if not exists repos('
                'repo text primary key, lang text, desc text, topics text,'
                'first_seen text, last_seen text, intro text, intro_at text)')
    cols = [r[1] for r in con.execute('pragma table_info(repos)')]
    for col in ('topics', 'intro', 'intro_at'):
        if col not in cols:
            con.execute('alter table repos add column %s text' % col)
    con.execute('create table if not exists list_items('
                'list text, date text, rank int, repo text, stars int, gained int,'
                'lang text, desc text, primary key(list, repo))')
    con.execute('create table if not exists judged('
                'repo text primary key, verdict text, at text, card_id text)')
    con.execute('create table if not exists meta(key text primary key, value text)')
    # 老库里只有 snapshots（日榜），一次性搬进 list_items，历史别丢
    if not con.execute("select value from meta where key='migrated_snapshots'").fetchone():
        try:
            for d, repo, stars, gained, rank in con.execute(
                    'select date,repo,stars,stars_today,rank from snapshots'):
                con.execute('insert or ignore into list_items(list,date,rank,repo,stars,gained,lang,desc)'
                            ' values(?,?,?,?,?,?,?,?)',
                            ('daily', d, rank or 0, repo, stars or 0, gained or 0, '', ''))
            con.execute("insert or replace into meta(key,value) values('migrated_snapshots','1')")
        except sqlite3.OperationalError:
            pass


def save_list(con, key, items, today):
    con.execute('delete from list_items where list=?', (key,))
    for i, it in enumerate(items, 1):
        repo = it['repo']
        con.execute('insert into repos(repo,lang,desc,topics,first_seen,last_seen) values(?,?,?,?,?,?)'
                    " on conflict(repo) do update set"
                    " lang=coalesce(nullif(excluded.lang,''), lang),"
                    " desc=coalesce(nullif(excluded.desc,''), desc),"
                    " topics=coalesce(nullif(excluded.topics,''), topics),"
                    " last_seen=excluded.last_seen",
                    (repo, it.get('lang', ''), it.get('desc', ''), it.get('topics', ''), today, today))
        con.execute('insert or replace into list_items(list,date,rank,repo,stars,gained,lang,desc)'
                    ' values(?,?,?,?,?,?,?,?)',
                    (key, today, i, repo, int(it.get('stars') or 0), int(it.get('gained') or 0),
                     it.get('lang', ''), it.get('desc', '')))


def set_meta(con, key, val):
    con.execute('insert or replace into meta(key,value) values(?,?)',
                (key, val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)))


def main():
    only = None
    for a in sys.argv[1:]:
        if a.startswith('--only='):
            only = set(x.strip() for x in a.split('=', 1)[1].split(',') if x.strip())
    today = date.today().isoformat()
    year_from = (date.today() - timedelta(days=365)).isoformat()
    con = sqlite3.connect(DB)
    ensure_schema(con)
    status = {}
    counts = {}

    for since in TRENDING:
        if only and since not in only:
            continue
        try:
            items = parse_trending(fetch_page(since))
            if not items:
                raise RuntimeError('解析到 0 条，页面结构可能变了')
            save_list(con, since, items, today)
            status[since] = 'ok'
            counts[since] = len(items)
        except Exception as e:
            status[since] = 'failed: %s' % str(e)[:160]
        time.sleep(1.0)

    api_jobs = []
    if not only or 'top100' in only:
        api_jobs.append(('top100', 'stars:>0'))
    if not only or 'year' in only:
        api_jobs.append(('year', 'created:>' + year_from))
    for key, q in api_jobs:
        try:
            items = fetch_search(q, 100)
            if not items:
                raise RuntimeError('API 返回 0 条')
            save_list(con, key, items, today)
            status[key] = 'ok'
            counts[key] = len(items)
        except Exception as e:
            status[key] = 'failed: %s' % str(e)[:160]
        time.sleep(1.0)

    set_meta(con, 'collect_status', status)
    set_meta(con, 'collect_counts', counts)
    set_meta(con, 'collected_at', datetime.now().strftime('%Y-%m-%d %H:%M'))
    set_meta(con, 'year_from', year_from)
    con.commit()
    con.close()

    out = {'ok': any(v == 'ok' for v in status.values()), 'date': today,
           'status': status, 'counts': counts}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
