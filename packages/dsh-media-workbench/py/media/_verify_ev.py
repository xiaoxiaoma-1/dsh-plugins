# -*- coding: utf-8 -*-
"""验收：检查 V3.2 给的 evidence 是不是原文原话（不是编的）"""
import json, re, sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect(r'E:\desktop\media\workbench.db')
res = json.load(open(r'E:\desktop\media\_quality_tier.json', encoding='utf-8'))

def norm(s):
    return re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', s or '')

o = []
hit = miss = 0
bad_books = []
for bid, r in res.items():
    title = c.execute('select title from books where id=?', (bid,)).fetchone()[0]
    full = norm(''.join(x[0] or '' for x in c.execute(
        'select content from book_chunks where book_id=?', (bid,))))
    line = ['%s | %s分 %s %s | %s' % (title[:40], r['score'], r['tier'],
            '完整' if r['intact'] else '抽坏', r['kind'])]
    for e in r.get('ev') or []:
        if norm(e) and norm(e) in full:
            hit += 1
            line.append('   ✔ 原文有：%s' % e)
        else:
            miss += 1
            line.append('   ✘ 原文查无：%s' % e)
    if any('✘' in x for x in line):
        bad_books.append(title[:40])
    o.append('\n'.join(line))

o.append('')
o.append('===== 汇总：evidence 命中 %d 条，查无 %d 条，命中率 %.1f%%' %
         (hit, miss, 100.0 * hit / max(1, hit + miss)))
o.append('有编造成分的书 %d 本' % len(bad_books))
open(r'E:\desktop\media\_verify_ev.txt', 'w', encoding='utf-8').write('\n'.join(o))
print('hit=%d miss=%d rate=%.1f%%' % (hit, miss, 100.0 * hit / max(1, hit + miss)))
