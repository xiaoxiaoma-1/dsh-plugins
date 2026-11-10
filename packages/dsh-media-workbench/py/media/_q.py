import sqlite3
c=sqlite3.connect(r'E:\desktop\media\workbench.db')
c.row_factory=sqlite3.Row
rows=c.execute("select post_id,title,audio_path from post_sources where audio_path is not null limit 5").fetchall()
for r in rows: print(r['post_id'],'|',(r['title'] or '')[:30],'|',r['audio_path'])
