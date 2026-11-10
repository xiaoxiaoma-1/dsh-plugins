import sqlite3
c=sqlite3.connect(r"E:\desktop\media\workbench.db")
rows=list(c.execute("select id,author,length(text),created_at from posts where text like '%拉开差距%' or author like '%大白话%' order by created_at"))
for r in rows: print(r)
print('total', len(rows))
