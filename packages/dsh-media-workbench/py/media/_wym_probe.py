# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect(r'E:\desktop\media\workbench.db')
o = []
rows = c.execute("""select b.id,b.title,b.author,coalesce(b.pages,0),coalesce(sum(length(cc.content)),0) n,
       count(cc.id) cnt, l.topic
   from books b left join book_chunks cc on cc.book_id=b.id
   left join book_labels l on l.book_id=b.id
   where b.title like '%王阳明%' or b.title like '%传习录%' or b.title like '%心学%' or b.title like '%知行合一%'
      or b.author like '%王阳明%' or b.title like '%阳明%'
   group by b.id order by n desc""").fetchall()
o.append('库里王阳明相关：%d 本' % len(rows))
for r in rows:
    tag = '空' if r[4] == 0 else ('碎片' if r[4] < 5000 else ('薄' if r[4] < 50000 else 'OK'))
    o.append('%s | %s字 %s页 %s块 | %s | %s' % (tag, r[4], r[3], r[5], (r[1] or '')[:56], r[2] or ''))
o.append('')
o.append('=== 关键词命中的重点候选 ===')
for kw in ['知易行难', '全集', '传习录', '心法', '大传', '全传']:
    rs = c.execute("select title, coalesce(sum(length(cc.content)),0) n from books b left join book_chunks cc on cc.book_id=b.id where title like ? group by b.id", ('%'+kw+'%',)).fetchall()
    o.append('【%s】%d 本: %s' % (kw, len(rs), ' / '.join(x[0][:24] for x in rs[:8])))
open(r'E:\desktop\media\_wangyangming.txt','w',encoding='utf-8').write('\n'.join(str(x) for x in o))
print('ok')
