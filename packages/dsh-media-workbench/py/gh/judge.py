# -*- coding: utf-8 -*-
"""记一条判断：这个项目「有用」还是「没用」。

有用 → 宿主插件已经往工作看板建了卡，card_id 记下来一起存。
没用 → 只记一条，以后榜单不再出现它。

用法：python judge.py --repo owner/name --verdict useful|useless [--card c123]
输出：一行 JSON
"""
import json
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
import os
import sqlite3
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'trending.db')


def main():
    repo = verdict = card = ''
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == '--repo' and i + 1 < len(args):
            repo = args[i + 1].strip()
        elif a == '--verdict' and i + 1 < len(args):
            verdict = args[i + 1].strip()
        elif a == '--card' and i + 1 < len(args):
            card = args[i + 1].strip()
    if not repo or verdict not in ('useful', 'useless'):
        print(json.dumps({'ok': False, 'error': '用法：--repo owner/name --verdict useful|useless'}, ensure_ascii=False))
        return
    con = sqlite3.connect(DB)
    try:
        con.execute('create table if not exists judged(repo text primary key, verdict text, at text, card_id text)')
        con.execute('insert or replace into judged(repo,verdict,at,card_id) values(?,?,?,?)',
                    (repo, verdict, datetime.now().strftime('%Y-%m-%d %H:%M'), card))
        con.commit()
    except Exception as e:
        print(json.dumps({'ok': False, 'error': str(e)[:200]}, ensure_ascii=False))
        return
    finally:
        con.close()
    print(json.dumps({'ok': True, 'repo': repo, 'verdict': verdict, 'card': card}, ensure_ascii=False))


if __name__ == '__main__':
    main()
