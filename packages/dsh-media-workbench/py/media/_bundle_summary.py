# -*- coding: utf-8 -*-
"""从汇编里抽结构摘要（给我自己做阶段0 理解用）"""
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"E:\desktop\书库盘点\_cangjie_input\内容创作.md"
txt = open(p, encoding="utf-8").read()
lines = txt.split("\n")

o = []
cur_sub = None
book_count = 0
buf = []
for i, ln in enumerate(lines):
    if ln.startswith("## 子类："):
        if cur_sub:
            o.append("\n")
        cur_sub = ln[4:].strip()
        o.append("=" * 60)
        o.append(cur_sub)
        book_count = 0
        continue
    if ln.startswith("### 《"):
        book_count += 1
        if book_count <= 3:
            o.append("  ▸ " + ln[4:].strip())
            buf = []
            j = i + 1
            got = 0
            while j < len(lines) and got < 320 and not lines[j].startswith("### ") and not lines[j].startswith("## 子类"):
                t = lines[j].strip()
                if t and not t.startswith("…"):
                    buf.append(t)
                    got += len(t)
                j += 1
            o.append("     " + " ".join(buf)[:300])
print("\n".join(o))
