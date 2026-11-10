# -*- coding: utf-8 -*-
import json, sys
sys.path.insert(0, r"E:\desktop\media")
sys.stdout.reconfigure(encoding="utf-8")
from wbquery import summary
d = summary()
print("ok:", d.get("ok"))
print("bySource:")
for x in d.get("bySource", []):
    print("   %-6s %5d 个 / %10d 字" % (x["key"], x["n"], x["chars"]))
print("recent:", d.get("recent"))
print("topics:", [(t["name"], t["n"]) for t in d.get("topics", [])])
print("tagTop:", [(t["name"], t["n"]) for t in d.get("tagTop", [])[:8]])
