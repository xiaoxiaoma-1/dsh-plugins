# -*- coding: utf-8 -*-
import sqlite3, json, io, os
c = sqlite3.connect(r'E:\desktop\media\workbench.db')
q = lambda s: c.execute(s).fetchall()
out = []
out.append('== books 1451, chunks %d' % q('select count(*) from book_chunks')[0][0])
out.append('== 字数字段合计: %d' % q('select sum(chars) from book_chunks')[0][0])
out.append('== 分类分布')
for r in q('select topic, count(*) from book_labels group by topic order by 2 desc'):
    out.append('   %s: %s' % (r[0], r[1]))
out.append('== 最短 10 本（字数升序）')
for r in q('select b.title, sum(c.chars) n, b.pages from books b join book_chunks c on c.book_id=b.id group by b.id order by n asc limit 12'):
    out.append('   %s | %s 字 | %s 页' % (r[0], r[1], r[2]))
out.append('== 最长 3 本')
for r in q('select b.title, sum(c.chars) n, b.pages from books b join book_chunks c on c.book_id=b.id group by b.id order by n desc limit 3'):
    out.append('   %s | %s 字 | %s 页' % (r[0], r[1], r[2]))
out.append('== 疑似 0 块/坏书 关键词搜')
for kw in ['知易行难', '阿里传', '王阳明']:
    rs = q("select id,title,pages from books where title like ?", ) if False else q("select id,title,pages from books where title like '%%%s%%'" % kw)
    for r in rs:
        n = q("select coalesce(sum(chars),0) from book_chunks where book_id='%s'" % r[0])[0][0]
        out.append('   [%s] %s | %s 页 | %s 字' % (kw, r[1], r[2], n))
out.append('== 每页平均字数 <100 的书（抽取不全嫌疑）')
rs = q('''select b.id,b.title,b.pages,c.chars,c.cnt from books b
          join (select book_id,sum(chars) chars,count(*) cnt from book_chunks group by book_id) c on c.book_id=b.id
          where b.pages>0 and (1.0*c.chars)/b.pages < 100''')
out.append('   共 %d 本' % len(rs))
for r in rs[:20]:
    out.append('   %s | %s 页 | %s 字 | %.1f 字/页' % (r[1], r[2], r[3], r[3]/r[2]))
out.append('== 目录存在性')
for p in [r'E:\desktop\media\_book_audit3.json', r'E:\wengao_原件回收_20261107', r'E:\wengao_碎片备份_20261107', r'E:\wengao', r'E:\wengao_新书']:
    out.append('   %s -> %s' % (p, os.path.exists(p)))
open(r'E:\desktop\media\_probe_out.txt', 'w', encoding='utf-8').write('\n'.join(str(x) for x in out))
print('written')

