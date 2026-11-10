"""把书库审计 json 生成可读清单（markdown）

输入：_book_audit_sample.json（全量跑完后是全库结果）
输出：书库审计清单.md（垃圾全列 / 一般全列 / 干货只列数量+少量样例）
"""
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
SRC = r"E:\desktop\media\_book_audit_sample.json"
OUT = r"E:\desktop\media\书库审计清单.md"

rows = json.load(open(SRC, encoding="utf-8"))
bad = [x for x in rows if x["useful"] == "垃圾"]
mid = [x for x in rows if x["useful"] == "一般"]
good = [x for x in rows if x["useful"] == "干货"]
fail = [x for x in rows if x["useful"] not in ("垃圾", "一般", "干货")]

def line(i, x):
    return f"| {i} | {x['title_old'][:28]} | {x['title_new'][:30]} | {x['kind']} | {x['why']} |"

with open(OUT, "w", encoding="utf-8") as f:
    f.write(f"# 书库审计清单（{len(rows)} 本）\n\n")
    f.write(f"- 垃圾（建议删）：**{len(bad)}** 本\n- 一般（你挑着删）：**{len(mid)}** 本\n"
            f"- 干货（留）：**{len(good)}** 本\n")
    if fail:
        f.write(f"- 解析失败：{len(fail)} 本\n")
    f.write("\n判定标准：干货=有具体方法/步骤/案例；一般=空泛重复价值有限；垃圾=目录页/版权页/乱码残页/无正文/纯虚构\n\n")

    f.write(f"## 一、垃圾（{len(bad)} 本，建议删）\n\n| # | 原名 | 重拟书名 | 类型 | 理由 |\n|---|---|---|---|---|\n")
    for i, x in enumerate(sorted(bad, key=lambda y: y["title_old"]), 1):
        f.write(line(i, x) + "\n")

    f.write(f"\n## 二、一般（{len(mid)} 本，挑着删）\n\n| # | 原名 | 重拟书名 | 类型 | 理由 |\n|---|---|---|---|---|\n")
    for i, x in enumerate(sorted(mid, key=lambda y: y["title_old"]), 1):
        f.write(line(i, x) + "\n")

    f.write(f"\n## 三、干货（{len(good)} 本，留）\n\n只列前 40 本样例：\n\n")
    f.write("| # | 原名 | 重拟书名 | 类型 | 理由 |\n|---|---|---|---|---|\n")
    for i, x in enumerate(sorted(good, key=lambda y: y["title_old"])[:40], 1):
        f.write(line(i, x) + "\n")

words = Counter(t for x in bad + mid for t in x["title_new"][:12].split())
print("垃圾", len(bad), "| 一般", len(mid), "| 干货", len(good), "| 失败", len(fail))
print("垃圾类型分布:", Counter(x["kind"] for x in bad).most_common())
print("清单:", OUT)
