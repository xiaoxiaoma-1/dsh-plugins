# -*- coding: utf-8 -*-
import sqlite3
c = sqlite3.connect(r'E:\desktop\media\workbench.db')
q = lambda s: c.execute(s).fetchall()
o = []

o.append('===== 一、165 本残书（<5000字）都是什么 =====')
rows = q('''select b.id, b.title, b.pages, sum(length(cc.content)) n, l.topic
  from books b
  join book_chunks cc on cc.book_id=b.id
  left join book_labels l on l.book_id=b.id
  group by b.id having n<5000 order by n''')
o.append('共 %d 本' % len(rows))
import re
groups = {}
for bid, t, p, n, topic in rows:
    t = t or ''
    if '付费文章' in t: k = '公众号付费文章合集'
    elif re.search(r'(第.{1,3}[讲课]|笔记|手稿|讲义|课堂)', t): k = '课程笔记/讲义'
    elif re.search(r'(脉轮|冥想|潜能|能量)', t): k = '灵修/冥想小册'
    elif re.search(r'(股票|筹码|成交量|多空|庄家|缠论|殷保华)', t): k = '炒股笔记'
    elif re.search(r'(微信|朋友圈|加好友|引流)', t): k = '微商/私域小技巧'
    elif re.search(r'(王阳明|心学|传习录)', t): k = '王阳明相关（多为精品网盘残件）'
    else: k = '其他'
    groups.setdefault(k, []).append((t, n, p, topic))
for k, v in sorted(groups.items(), key=lambda x: -len(x[1])):
    o.append('')
    o.append('【%s】%d 本' % (k, len(v)))
    for t, n, p, topic in v[:12]:
        o.append('   %s | %d字 %s页 | %s' % (t[:52], n, p, topic))
    if len(v) > 12: o.append('   ...另 %d 本' % (len(v)-12))

o.append('')
o.append('===== 二、chars 字段 4 万行 NULL 的原因 =====')
o.append('NULL 行数: %s' % q('select count(*) from book_chunks where chars is null')[0][0])
o.append('有值行数: %s' % q('select count(*) from book_chunks where chars is not null')[0][0])
o.append('NULL 行按入库日期分布:')
for r in q("""select date(created_at/1000,'unixepoch','+8 hours') d, count(*) from book_chunks
              where chars is null group by d order by d"""):
    o.append('   %s : %s 行' % (r[0], r[1]))
o.append('有值行按入库日期分布:')
for r in q("""select date(created_at/1000,'unixepoch','+8 hours') d, count(*) from book_chunks
              where chars is not null group by d order by d"""):
    o.append('   %s : %s 行' % (r[0], r[1]))
o.append('抽查 NULL 行的内容长度是否正常:')
for r in q('select id, book_id, length(content) from book_chunks where chars is null limit 5'):
    o.append('   id=%s len=%s' % (r[0], r[2]))

o.append('')
o.append('===== 三、17 本抽取不全明细 =====')
for r in q('''select b.title,b.pages,c.n,c.cnt from books b
   join (select book_id,sum(length(content)) n,count(*) cnt from book_chunks group by book_id) c on c.book_id=b.id
   where b.pages>0 and (1.0*c.n)/b.pages < 100 order by (1.0*c.n)/b.pages'''):
    o.append('   %s | %s页 %d字 %d块 | %.1f字/页' % (r[0][:52], r[1], r[2], r[3], r[2]/r[1]))

open(r'E:\desktop\media\_probe_out3.txt','w',encoding='utf-8').write('\n'.join(str(x) for x in o))
print('ok')
