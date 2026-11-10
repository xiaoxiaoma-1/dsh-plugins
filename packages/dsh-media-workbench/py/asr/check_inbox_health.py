# -*- coding: utf-8 -*-
"""私信投递箱健康检查：超过 N 小时没有新的抖音入库就报警。

用法：
  python check_inbox_health.py            # 只看，返回码 0=正常 1=告警
  python check_inbox_health.py --push     # 告警时顺带推给桌宠（/pet/push）
"""
import sqlite3, sys, json, os, datetime, urllib.request

DB = r'E:\desktop\media\workbench.db'
THRESHOLD_HOURS = 24
STATE = r'E:\tools\asr\out\inbox_health.json'


def latest():
    c = sqlite3.connect(DB)
    row = c.execute("select max(created_at) from posts where kind='douyin'").fetchone()
    c.close()
    return row[0] if row else None


def push_pet(title, detail):
    for port in (49170,):
        try:
            body = json.dumps({'id': 'inbox-health', 'title': title, 'detail': detail,
                               'state': 'running', 'pct': 0}).encode('utf-8')
            req = urllib.request.Request('http://127.0.0.1:%d/pet/push' % port, data=body,
                                         headers={'Content-Type': 'application/json'}, method='POST')
            urllib.request.urlopen(req, timeout=3).read()
            return True
        except Exception:
            continue
    return False


def main():
    ts = latest()
    now = datetime.datetime.now()
    info = {'checkedAt': now.strftime('%Y-%m-%dT%H:%M:%S'), 'latestIngest': ts}
    if not ts:
        info.update({'ok': False, 'reason': 'no-douyin-posts'})
    else:
        try:
            last = datetime.datetime.fromisoformat(ts)
        except ValueError:
            last = now
        hours = (now - last).total_seconds() / 3600
        info['hoursSince'] = round(hours, 1)
        info['ok'] = hours < THRESHOLD_HOURS
        if not info['ok']:
            info['reason'] = 'stale-%sh' % round(hours)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(json.dumps(info, ensure_ascii=False))
    if not info['ok'] and '--push' in sys.argv:
        push_pet('私信投递箱断了', '已经 %s 小时没有新的抖音内容入库' % info.get('hoursSince'))
    return 0 if info['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
