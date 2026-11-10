# -*- coding: utf-8 -*-
"""给工作台插件输出 GitHub 榜单 JSON（五张榜 + 每条的 AI 简介）。

用法：python query.py
输出：一行 JSON（runPyJson 只取最后一行）

判断过的项目（judged 表）不再出现在榜单里：判「有用」的已经进看板，判「没用」的直接消失。
"""
import json
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'trending.db')

# 只有命中这些「真·工具型能力」才隐藏；技能包/方法论/提示词合集不隐藏（容易误杀）
DUP_HIDE = {
    'Chrome 控制', '心印 · 跨会话记忆', '设计品味技能', '超级搜索', '免费模型网关',
    '智能工作看板', '微信桥', '通话面板', '逆向分析 REA', '紫微斗数工作台',
    '自媒体工作台 · 需求发掘台',
}

# list key, 标题, 副标题, 数字单位, 默认展开
LISTS = [
    ('daily', '今日涨星榜', '按今天新增星数排', '今天', True),
    ('weekly', '本周涨星榜', '按最近 7 天新增星数排', '本周', False),
    ('monthly', '本月涨星榜', '按最近 30 天新增星数排', '本月', False),
    ('year', '近一年新秀榜', '近一年新建的仓库，按攒到的星排', '', False),
    ('top100', '总星 Top 100', '全站星最多的仓库，不常变', '', False),
]


def parse_intro(raw):
    if not raw:
        return None
    try:
        j = json.loads(raw)
        if isinstance(j, dict) and j.get('what'):
            return {'what': str(j.get('what'))[:80], 'use': str(j.get('use') or '')[:80]}
    except Exception:
        pass
    return None


def main():
    if not os.path.exists(DB):
        print(json.dumps({'ok': False, 'error': '还没有数据，先采集一次'}, ensure_ascii=False))
        return
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        con.execute('create table if not exists judged(repo text primary key, verdict text, at text, card_id text)')
        con.execute("create table if not exists meta(key text primary key, value text)")
        judged = {r['repo']: r['verdict'] for r in con.execute('select repo,verdict from judged')}
        meta = {r['key']: r['value'] for r in con.execute('select key,value from meta')}
        collected_at = meta.get('collected_at') or ''
        year_from = meta.get('year_from') or ''
        try:
            collect_status = json.loads(meta.get('collect_status') or '{}')
        except Exception:
            collect_status = {}

        lists = {}
        daily = []
        pending = 0
        seen_missing = set()
        for key, label, sub, unit, default_open in LISTS:
            rows = con.execute(
                'select i.rank,i.repo,i.stars,i.gained,i.lang,i.desc,'
                ' coalesce(r.intro, \'\') as intro, coalesce(r.dup, \'\') as dup'
                ' from list_items i left join repos r on r.repo=i.repo'
                ' where i.list=? order by i.rank', (key,)).fetchall()
            items = []
            skipped = []
            total_gain = 0
            missing = 0
            for r in rows:
                if r['repo'] in judged:
                    continue
                try:
                    dup = json.loads(r['dup'] or '{}')
                except Exception:
                    dup = {}
                if dup.get('name') in DUP_HIDE and float(dup.get('conf') or 0) >= 0.85:
                    skipped.append({'repo': r['repo'], 'name': dup.get('name'), 'why': dup.get('why') or ''})
                    continue
                intro = parse_intro(r['intro'])
                if not intro and r['repo'] not in seen_missing:
                    seen_missing.add(r['repo'])
                    pending += 1
                if not intro:
                    missing += 1
                total_gain += int(r['gained'] or 0)
                items.append({
                    'repo': r['repo'],
                    'lang': r['lang'] or '',
                    'desc': r['desc'] or '',
                    'stars': int(r['stars'] or 0),
                    'gained': int(r['gained'] or 0),
                    'rank': r['rank'],
                    'intro': intro,
                })
            lists[key] = {
                'key': key, 'label': label, 'sub': sub, 'unit': unit,
                'defaultOpen': default_open, 'count': len(items),
                'totalGain': total_gain, 'missing': missing, 'items': items,
                'skippedDup': skipped,
            }
            if key != 'daily':
                continue
            # 日榜顺带出统计
            daily = items

        total = sum(i['gained'] for i in daily)
        langs = {}
        for i in daily:
            k = i['lang'] or '未标注'
            langs[k] = langs.get(k, 0) + 1
        langs = sorted(langs.items(), key=lambda x: -x[1])
        days = con.execute("select count(distinct date) from list_items where list='daily'").fetchone()[0]
        first_day = con.execute("select min(date) from list_items where list='daily'").fetchone()[0] or ''
        snap_date = con.execute("select max(date) from list_items where list='daily'").fetchone()[0] or ''
        useful = sum(1 for v in judged.values() if v == 'useful')
        useless = sum(1 for v in judged.values() if v == 'useless')
    except Exception as e:
        con.close()
        print(json.dumps({'ok': False, 'error': str(e)[:300]}, ensure_ascii=False))
        return
    con.close()

    out = {
        'ok': True,
        'date': snap_date,
        'collectedAt': collected_at,
        'yearFrom': year_from,
        'pendingIntro': pending,
        'collectStatus': collect_status,
        'counts': {'useful': useful, 'useless': useless},
        'stats': {
            'count': len(daily),
            'total': total,
            'avg': round(total / len(daily)) if daily else 0,
            'topLang': langs[0][0] if langs else '—',
            'langs': [{'name': k, 'n': v} for k, v in langs],
            'days': days,
            'firstDay': first_day,
        },
        'lists': lists,
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
