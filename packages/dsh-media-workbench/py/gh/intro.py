# -*- coding: utf-8 -*-
"""给榜单里的项目生成中文简介，并和本机已装的 DSH 插件比对是否功能重复。

两件事都只做一次，结果存进 repos 表，之后榜单复用：
  intro   {"what": "...", "use": "..."}   干什么 / 能做什么
  dup     ""（不重复）或 {"name": "插件名", "why": "为什么重复"}

模型走本机 OpenAI 兼容网关（默认 http://127.0.0.1:8326/v1）。
调用顺序：先把没简介的补简介；补完了再给有简介、没比对过的做去重。

用法：python intro.py [--list=daily] [--limit=8]
输出：一行 JSON {ok, generated, remaining, intros, duped, dupRemaining, dups, error?}
"""
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'trending.db')
DSH_HOME = os.environ.get('DSH_HOME') or os.path.join(os.path.expanduser('~'), '.dsh')
PROFILE = os.path.join(DSH_HOME, 'profiles', 'desktop')

BASE = (os.environ.get('DSH_INTRO_BASE') or 'http://127.0.0.1:8326/v1').rstrip('/')
MODEL = os.environ.get('DSH_INTRO_MODEL') or 'siliconflow/deepseek-ai/DeepSeek-V3.2'
KEY = (os.environ.get('DSH_INTRO_KEY') or '').strip()
if not KEY:
    key_file = (os.environ.get('DSH_INTRO_KEY_FILE') or '').strip()
    if key_file and os.path.exists(key_file):
        try:
            KEY = open(key_file, encoding='utf-8').read().strip()
        except Exception:
            KEY = ''

ORDER = ['daily', 'weekly', 'monthly', 'year', 'top100']

# 已装能力的中文名 + 一句话用途。没列到的插件读它自己的 package.json 描述。
KNOWN = {
    'my-memory': ('心印 · 跨会话记忆', '七层长期记忆、经验包、进度交接、记忆脉络图'),
    'dsh-work-board': ('智能工作看板', '四栏看板（待完成/进行中/阶段完成/已完成），卡片能绑对话'),
    'dsh-workbench-hub': ('工作台合集', '侧栏「工作台」入口，里面是自媒体台 / 算命台 / 需求发掘台'),
    'dsh-media-workbench': ('自媒体工作台 · 需求发掘台', '采集、稿库、文案拆解、选题，以及 GitHub 热榜和需求判断'),
    'dsh-chrome-control': ('Chrome 控制', '让 AI 操作用户真实的 Chrome：开页面、点击、读内容、截图'),
    'dsh-plugin-ai-super-search': ('超级搜索', '免 key 网页搜索（TinyFish / Bing / Jina / DuckDuckGo）'),
    'dsh-our-free-model': ('免费模型网关', '本机 OpenAI 兼容网关 + 多家免费/匿名模型渠道'),
    'dsh-agent-teams': ('Agent 团队', '多智能体协作：队长、队员、任务依赖、消息'),
    'dsh-wechat': ('微信桥', '用微信和 DSH 聊天、收文件'),
    'dsh-call': ('通话面板', '全屏语音对话，说完自动提问、回复自动朗读'),
    'dsh-ziwei': ('紫微斗数工作台', '排盘 + AI 解读'),
    'dsh-rea': ('逆向分析 REA', 'exe/apk/asar 静态分析、域名扫描、报告'),
    'dsh-design-skills': ('设计品味技能', 'impeccable / taste-skill：前端设计审查与美术指导'),
    'dsh-ponytail-lazy': ('懒人编码原则', '少写废话、精炼代码'),
    'dsh-experimental-auto-review': ('工具授权审查', '自动审查工具调用有没有风险'),
    'dsh-experimental-inspector-profile': ('会话检查器', '看原始会话日志和节点'),
    'dsh-experimental-session-search': ('历史会话检索', '搜索并读取以前的会话'),
}
CORE = ('DSH 本体', '文件读写、终端命令、子智能体、工作流、定时任务、MCP 资源、网页搜索')

SYS = ('你在帮一个不懂编程的中文用户筛选 GitHub 项目。他看完你写的两句话，要能立刻判断'
       '「这东西跟我有没有关系」。说人话，可以打比方，不堆术语。')

TPL = '''下面这些是 GitHub 上的项目。对每个项目写两句话：
1. what：它到底是什么（30 字内，大白话）
2. use：普通人或独立开发者拿它能干什么（30 字内，要具体到场景；如果只对程序员有用，就直说「给程序员写代码用」）

不许用这些词：赋能、一站式、强大、极致、生态、革命性、颠覆、利器。
信息不够就写「描述太少，看不出能干什么」，不要编。

只输出 JSON 数组，不要解释、不要代码块：
[{"repo":"owner/name","what":"…","use":"…"}]

项目：
'''

SYS2 = ('你在帮一个中文用户过滤 GitHub 榜单：他已经装了下面这些 DSH 插件和能力。'
        '功能重复的项目不要占他的注意力。判断保守一点，拿不准就说不重复。')

TPL2 = '''他已经有的能力：
{inv}

下面是榜单项目，每个已经有一句简介。判断：装上它之后，他的能力会不会「实质增加」？
判重复的门槛要严：
- 只有「装了它，用户已有的能力没有实质增加」才算重复；
- 能互补、能搭配、只是同属 AI/开发工具，都不算重复；
- 技能包、提示词包、素材包、内容合集，都不算重复——它们是内容，装进去是给已有机制喂料，能力会增加；
- 操作对象不同也不算（比如一个管浏览器、一个管整个桌面）；
- 拿不准就不算重复。宁可漏判，也不要误杀。
- dup 只能从上面清单里原样挑一个名字，不重复就留空字符串。
- conf 是 0 到 1 的小数：你有多确定「装了它用户能力不增加」。只有 conf>=0.8 才会被隐藏，拿不准写 0.5。

只输出 JSON 数组，不要解释：
[{"repo":"owner/name","dup":"清单里的名字或空","why":"一句话；不重复就空","conf":0.0}]

项目：
'''


def ensure_cols(con):
    cols = [r[1] for r in con.execute('pragma table_info(repos)')]
    for col in ('dup', 'dup_at'):
        if col not in cols:
            con.execute('alter table repos add column %s text' % col)
    con.execute('create table if not exists judged(repo text primary key, verdict text, at text, card_id text)')


def load_inventory():
    """从当前 profile 的依赖里拼出「已装能力」清单。"""
    entries = [CORE]
    seen = set()
    try:
        with open(os.path.join(PROFILE, 'package.json'), encoding='utf-8') as f:
            pkg = json.load(f)
        deps = list((pkg.get('dependencies') or {}).keys())
        bundles = ((pkg.get('dsh') or {}).get('profile') or {}).get('bundles') or []
        for name in bundles + deps:
            short = name.split('/')[-1]
            if name.startswith('@deepseek-ai/dsh-base') or name.startswith('@deepseek-ai/dsh-web-app'):
                continue
            if short in seen:
                continue
            seen.add(short)
            if short in KNOWN:
                entries.append(KNOWN[short])
                continue
            desc = ''
            try:
                p = os.path.join(PROFILE, 'node_modules', name, 'package.json')
                with open(p, encoding='utf-8') as f:
                    desc = (json.load(f).get('description') or '').strip()
            except Exception:
                pass
            if desc:
                entries.append((short, desc[:110]))
    except Exception:
        pass
    if len(entries) <= 1:
        entries += [v for k, v in KNOWN.items()]
    return entries


def inv_text():
    return '\n'.join('- %s：%s' % (n, d) for n, d in load_inventory())


def pick_items(con, limit, only_list=''):
    rows = []
    keys = [only_list] if only_list in ORDER else ORDER
    for key in keys:
        for r in con.execute(
                'select i.repo, i.lang, i.desc, i.stars, coalesce(r.topics,\'\') as topics'
                ' from list_items i left join repos r on r.repo=i.repo'
                ' where i.list=? and r.intro is null'
                ' order by i.rank limit ?', (key, limit)).fetchall():
            rows.append(dict(r))
            if len(rows) >= limit:
                return rows
    return rows


def pick_dup_items(con, limit, only_list=''):
    rows = []
    seen = set()
    keys = [only_list] if only_list in ORDER else ORDER
    for key in keys:
        for r in con.execute(
                'select i.repo, r.intro from list_items i left join repos r on r.repo=i.repo'
                ' where i.list=? and r.intro is not null and r.dup_at is null'
                ' order by i.rank', (key,)).fetchall():
            if r['repo'] in seen:
                continue
            seen.add(r['repo'])
            rows.append({'repo': r['repo'], 'intro': r['intro']})
            if len(rows) >= limit:
                return rows
    return rows


def count_missing(con, only_list='', phase='intro'):
    if phase == 'intro':
        q = ('select count(distinct i.repo) from list_items i left join repos r on r.repo=i.repo'
             ' where r.intro is null')
        if only_list in ORDER:
            return con.execute(q + ' and i.list=?', (only_list,)).fetchone()[0]
        return con.execute(q).fetchone()[0]
    q = ('select count(distinct i.repo) from list_items i left join repos r on r.repo=i.repo'
         ' where r.intro is not null and r.dup_at is null')
    if only_list in ORDER:
        return con.execute(q + ' and i.list=?', (only_list,)).fetchone()[0]
    return con.execute(q).fetchone()[0]


def chat(messages, max_tokens=1600):
    body = {
        'model': MODEL, 'temperature': 0.4, 'max_tokens': max_tokens,
        'messages': messages,
    }
    req = urllib.request.Request(
        BASE + '/chat/completions',
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + KEY},
        method='POST')
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode('utf-8'))
    return (data.get('choices') or [{}])[0].get('message', {}).get('content') or ''


def parse_json_array(text):
    text = text.strip()
    text = re.sub(r'^```(?:json)?', '', text).strip()
    text = re.sub(r'```$', '', text).strip()
    i, j = text.find('['), text.rfind(']')
    if i < 0 or j <= i:
        return []
    try:
        arr = json.loads(text[i:j + 1])
    except Exception:
        return []
    return [it for it in arr if isinstance(it, dict)] if isinstance(arr, list) else []


def parse_intro(text):
    out = []
    for it in parse_json_array(text):
        repo = str(it.get('repo') or '').strip()
        what = str(it.get('what') or '').strip()
        use = str(it.get('use') or '').strip()
        if repo and what:
            out.append({'repo': repo, 'what': what[:80], 'use': use[:80]})
    return out


def parse_dup(text):
    out = []
    for it in parse_json_array(text):
        repo = str(it.get('repo') or '').strip()
        if not repo:
            continue
        dup = str(it.get('dup') or '').strip()
        why = str(it.get('why') or '').strip()
        try:
            conf = float(it.get('conf') or 0)
        except Exception:
            conf = 0
        out.append({'repo': repo, 'dup': dup[:60], 'why': why[:120], 'conf': max(0.0, min(1.0, conf))})
    return out


def intro_lines(items):
    lines = []
    for it in items:
        bits = ['- %s' % it['repo']]
        if it['lang']:
            bits.append('[' + it['lang'] + ']')
        if it['stars']:
            bits.append('★%s' % it['stars'])
        bits.append('：' + (it['desc'] or ''))
        if it['topics']:
            bits.append('（标签：' + it['topics'] + '）')
        lines.append(''.join(bits))
    return lines


def dup_lines(items):
    lines = []
    for it in items:
        intro = {}
        try:
            intro = json.loads(it['intro'] or '{}')
        except Exception:
            intro = {}
        what = intro.get('what') or ''
        use = intro.get('use') or ''
        lines.append('- %s：%s；%s' % (it['repo'], what, use))
    return lines


def run_phase(con, phase, items):
    """跑一轮模型调用，写库，返回 (stored_map, err)。"""
    now = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')
    by_repo = {it['repo'] for it in items}
    err = ''
    if phase == 'intro':
        messages = [{'role': 'system', 'content': SYS},
                    {'role': 'user', 'content': TPL + '\n'.join(intro_lines(items))}]
    else:
        messages = [{'role': 'system', 'content': SYS2},
                    {'role': 'user', 'content': TPL2.replace('{inv}', inv_text()) + '\n'.join(dup_lines(items))}]
    got = []
    for attempt in range(2):
        try:
            got = parse_intro(chat(messages)) if phase == 'intro' else parse_dup(chat(messages, 1200))
            if got:
                break
            err = '模型返回的不是 JSON 数组'
        except urllib.error.HTTPError as e:
            err = '模型接口 %s：%s' % (e.code, e.read().decode('utf-8', 'replace')[:200])
        except Exception as e:
            err = '模型调用失败：%s' % str(e)[:200]
    stored = {}
    if phase == 'intro':
        for it in got:
            if it['repo'] not in by_repo:
                continue
            con.execute('update repos set intro=?, intro_at=? where repo=?',
                        (json.dumps({'what': it['what'], 'use': it['use']}, ensure_ascii=False),
                         now, it['repo']))
            stored[it['repo']] = {'what': it['what'], 'use': it['use']}
    else:
        for it in got:
            if it['repo'] not in by_repo:
                continue
            payload = json.dumps({'name': it['dup'], 'why': it['why'], 'conf': it['conf']}, ensure_ascii=False) if it['dup'] else ''
            con.execute('update repos set dup=?, dup_at=? where repo=?', (payload, now, it['repo']))
            stored[it['repo']] = {'name': it['dup'], 'why': it['why'], 'conf': it['conf']}
    con.commit()
    return stored, err


def main():
    limit = 8
    only_list = ''
    for a in sys.argv[1:]:
        if a.startswith('--list='):
            only_list = a.split('=', 1)[1].strip()
        elif a.startswith('--limit='):
            try:
                limit = max(1, min(20, int(a.split('=', 1)[1])))
            except Exception:
                pass
    if not os.path.exists(DB):
        print(json.dumps({'ok': False, 'error': '还没有榜单数据'}, ensure_ascii=False))
        return
    if not KEY:
        print(json.dumps({'ok': False, 'error': '没有模型 key（DSH_INTRO_KEY / DSH_INTRO_KEY_FILE）'}, ensure_ascii=False))
        return
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        ensure_cols(con)
        out = {'ok': True, 'generated': 0, 'remaining': count_missing(con, only_list, 'intro'),
               'intros': {}, 'duped': 0, 'dupRemaining': count_missing(con, only_list, 'dup'), 'dups': {}}
        items = pick_items(con, limit, only_list)
        if items:
            stored, err = run_phase(con, 'intro', items)
            out['generated'] = len(stored)
            out['intros'] = stored
            out['remaining'] = count_missing(con, only_list, 'intro')
            out['dupRemaining'] = count_missing(con, only_list, 'dup')
            if err and not stored:
                out['ok'] = False
                out['error'] = err
            print(json.dumps(out, ensure_ascii=False))
            return

        dups = pick_dup_items(con, min(limit, 10), only_list)
        if not dups:
            print(json.dumps(out, ensure_ascii=False))
            return
        stored, err = run_phase(con, 'dup', dups)
        out['duped'] = len(stored)
        out['dups'] = stored
        out['dupRemaining'] = count_missing(con, only_list, 'dup')
        if err and not stored:
            out['ok'] = False
            out['error'] = err
        print(json.dumps(out, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'ok': False, 'error': str(e)[:300]}, ensure_ascii=False))
    finally:
        con.close()


if __name__ == '__main__':
    main()
