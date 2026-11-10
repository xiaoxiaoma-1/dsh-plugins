import sqlite3
c=sqlite3.connect(r"E:\desktop\media\workbench.db")
print(list(c.execute("select kind,count(*) from posts group by kind")))
