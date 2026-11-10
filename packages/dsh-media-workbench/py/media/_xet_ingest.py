# -*- coding: utf-8 -*-
"""把转录结果写入文稿库 workbench.db（posts + post_sources），并生成合并 md"""
import json, os, sqlite3, time, datetime

DB = r'E:\desktop\media\workbench.db'
TXT = r'E:\desktop\media\_xet_text'
MAN = r'E:\desktop\media\_xet_manifest.json'
AUTHOR = '小年自媒体系统课'
KIND = '课程'
TODAY = datetime.date.today().isoformat()

man = json.load(open(MAN, encoding='utf-8'))
rows = []
for rec in man:
    if not rec.get('ok'):
        continue
    base = os.path.splitext(rec['file'])[0] if rec.get('file') else None
    if not base:
        continue
    jp = os.path.join(TXT, base + '.json')
    if not os.path.exists(jp):
        print('MISS_JSON', base)
        continue
    d = json.load(open(jp, encoding='utf-8'))
    rows.append({
        'pid': 'xet_' + rec['rid'],
        'idx': rec['idx'],
        'author': AUTHOR,
        'date': TODAY,
        'kind': KIND,
        'text': d['plain'],
        'url': 'https://appae4y5du51721.h5.xiaoeknow.com/p/course/video/' + rec['rid'],
        'platform': '小鹅通',
        'title': rec['title'],
        'vid': rec['rid'],
        'duration': d.get('duration') or rec.get('sec') or 0,
        'audio_path': os.path.join(r'E:\desktop\media\_xet_audio', rec['file']),
        'chars': d.get('chars') or len(d['plain']),
        'segments': d.get('segments') or [],
    })

print('ready', len(rows))
c = sqlite3.connect(DB)
now = datetime.datetime.now().isoformat(timespec='seconds')
for r in rows:
    c.execute('delete from posts where id=?', (r['pid'],))
    c.execute('insert into posts (id,author,date,kind,text,url,created_at,hidden,topic_override) values (?,?,?,?,?,?,?,0,NULL)',
              (r['pid'], r['author'], r['date'], r['kind'], r['text'], r['url'], now))
    c.execute('delete from post_sources where post_id=?', (r['pid'],))
    c.execute('insert into post_sources (post_id,platform,title,vid,duration,audio_path,created_at) values (?,?,?,?,?,?,?)',
              (r['pid'], r['platform'], r['title'], r['vid'], r['duration'], r['audio_path'], now))
c.commit()
n_posts = c.execute("select count(*) from posts where kind=?", (KIND,)).fetchone()[0]
n_src = c.execute("select count(*) from post_sources where platform='小鹅通'").fetchone()[0]
c.close()
print('posts(kind=课程)=%d post_sources(小鹅通)=%d' % (n_posts, n_src))

# 合并 md
out = ['# 小年自媒体系统课 · 全课逐字稿', '',
       '- 课程：小鹅通《小年自媒体系统课》',
       '- 章节：%d 节，总时长 %d 分钟' % (len(rows), round(sum(r['duration'] for r in rows) / 60)),
       '- 生成时间：%s' % now, '']
toc = []
for i, r in enumerate(sorted(rows, key=lambda x: x['idx']), 1):
    m = int(r['duration'] // 60); s = int(r['duration'] % 60)
    toc.append('%d. %s（%d分%d秒）' % (i, r['title'], m, s))
out += ['## 目录', ''] + toc + ['']
for i, r in enumerate(sorted(rows, key=lambda x: x['idx']), 1):
    m = int(r['duration'] // 60); s = int(r['duration'] % 60)
    out += ['---', '', '## %d. %s' % (i, r['title']), '',
            '> 时长 %d分%d秒 · %d 字' % (m, s, r['chars']), '', r['text'], '']
    out += ['### 逐句'] + ['']
    for sg in r['segments']:
        t = int(sg['s'])
        out.append('[%02d:%02d] %s' % (t // 60, t % 60, sg['t']))
    out.append('')
open(os.path.join(TXT, '_全部逐字稿.md'), 'w', encoding='utf-8').write('\n'.join(out))
print('merged md ->', os.path.join(TXT, '_全部逐字稿.md'), os.path.getsize(os.path.join(TXT, '_全部逐字稿.md')), 'bytes')
