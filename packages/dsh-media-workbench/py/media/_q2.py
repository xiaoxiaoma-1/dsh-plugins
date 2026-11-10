import sqlite3
c=sqlite3.connect(r"E:\desktop\media\workbench.db")
r=c.execute("select id,author,length(text) from posts where id='dy_7704227871669226792'").fetchone()
print(r)
