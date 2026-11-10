# -*- coding: utf-8 -*-
import sqlite3
c = sqlite3.connect(r'E:\desktop\media\workbench.db')
q = lambda s: c.execute(s).fetchall()
o = []
o.append('== chars 字段 vs length(content) 差异')
o.append('   sum(chars)=%s' % q('select sum(chars) from book_chunks')[0][0])
o.append('   sum(length(content))=%s' % q('select sum(length(content)) from book_chunks')[0][0])
o.append('   chars 为 NULL 的行=%s' % q('select count(*) from book_chunks where chars is null')[0][0])
o.append('   chars=0 的行=%s' % q('select count(*) from book_chunks where chars=0')[0][0])
o.append('== 按 length(content) 重算：真正 0 字的书')
zero = q('''select b.id,b.title,b.pages from books b where not exists
   (select 1 from book_chunks c where c.book_id=b.id and length(trim(c.content))>0)''')
o.append('   共 %d 本' % len(zero))
for r in zero[:40]:
    o.append('   %s | %s 页' % (r[1], r[2]))
o.append('== 真正总字数（length）%s' % q('select sum(length(content)) from book_chunks')[0][0])
o.append('== 每页平均 <100 字的书（length 口径）')
rs = q('''select b.title,b.pages,c.n,c.cnt from books b
   join (select book_id,sum(length(content)) n,count(*) cnt from book_chunks group by book_id) c on c.book_id=b.id
   where b.pages>0 and (1.0*c.n)/b.pages < 100 order by (1.0*c.n)/b.pages''')
o.append('   共 %d 本' % len(rs))
for r in rs[:30]:
    o.append('   %s | %s 页 | %d 字 | %.1f 字/页' % (r[0], r[1], r[2], r[2]/r[1]))
o.append('== 字数 <5000 的书（length 口径）')
rs5 = q('''select b.title,c.n,b.pages from books b
   join (select book_id,sum(length(content)) n from book_chunks group by book_id) c on c.book_id=b.id
   where c.n<5000 order by c.n''')
o.append('   共 %d 本' % len(rs5))
for r in rs5[:40]:
    o.append('   %s | %d 字 | %s 页' % (r[0], r[1], r[2]))
o.append('== 标题乱码检测（含高位奇形字符）')
moj = q("select title from books")
bad = [t[0] for t in moj if t[0] and any(ch in t[0] for ch in '╢╝┼╔╩╓╥╞╬')]
o.append('   疑似 GBK 乱码标题 %d 本' % len(bad))
for t in bad[:10]:
    o.append('   ' + t[:60])
open(r'E:\desktop\media\_probe_out2.txt','w',encoding='utf-8').write('\n'.join(str(x) for x in o))
print('ok')
