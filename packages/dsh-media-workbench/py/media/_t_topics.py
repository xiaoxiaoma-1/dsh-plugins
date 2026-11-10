import sqlite3, json, sys
db, limit = sys.argv[1], int(sys.argv[2])
c = sqlite3.connect(db)
rows = c.execute("select id, day, title, angle, hook, score, level, board from pool_topics where (status is null or status not in ('used','archived')) order by day desc, score desc limit ?", (limit,)).fetchall()
out = [{"id": r[0], "day": r[1], "title": r[2], "angle": r[3], "hook": r[4], "score": r[5], "level": r[6], "board": r[7]} for r in rows]
print(json.dumps({"topics": out}, ensure_ascii=False))
