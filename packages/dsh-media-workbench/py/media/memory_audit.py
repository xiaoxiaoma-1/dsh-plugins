# -*- coding: utf-8 -*-
r"""记忆审计：找出「用户重复纠正、我还在犯」的主题，输出成给人看的报告。

用法：
  python memory_audit.py            # 扫一次，写报告
  python memory_audit.py --print    # 扫一次，直接打印

输出：E:\desktop\media\_memory_audit.md

判据：
- 只扫带 corrected / 用户纠正 / 用户要求 / 用户强调 标签的记忆
- 按标题里的高频主题词聚类
- 一个主题出现 >= 3 次 = 用户为这件事纠正过我 3 次以上
- 报告里会对照 AGENTS.md 的自检清单，标出「已进自检」和「还没进」的
"""
import io
import os
import re
import sqlite3
import sys
import time
from collections import Counter

DB = r"C:\Users\Administrator\.my-memory\memory.db"
OUT = r"E:\desktop\media\_memory_audit.md"
AGENTS = r"E:\DSH-data\.dsh\AGENTS.md"
LEVELS = ("lesson", "rules", "fact", "project", "user", "topic", "soul")

# 停用词：出现在标题里但没有主题意义的
STOP = set("""用户 纠正 要求 强调 不要 必须 不能 记住 这个 那个 我的 就是 记录 注意 问题
一条 每次 已经 现在 以后 时候 什么 怎么 为什 么样 还是 不是 可以 应该 需要 情况 发现
严重 重要 千万 一定 记得 别再 再次 下次 之一 之后 之前 说明 内容 文件 数据""".split())

if sys.stdout is None or sys.stderr is None:
    _n = open(os.devnull, "w")
    sys.stdout = sys.stdout or _n
    sys.stderr = sys.stderr or _n
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_corrected(c):
    rows = []
    for lv in LEVELS:
        try:
            cur = c.execute(f"select id, title, tags, importance, content from {lv}")
        except Exception:
            continue
        for r in cur:
            tg = r[2] or ''
            if any(k in tg for k in ('corrected', '用户纠正', '用户要求', '用户强调')):
                rows.append({'id': r[0], 'level': lv, 'title': r[1] or '',
                             'imp': r[3] or 0, 'content': (r[4] or '')[:200]})
    return rows


def theme_of(title):
    """从标题里抽主题词（2-6 个汉字的名词性片段）"""
    words = re.findall(r'[\u4e00-\u9fa5]{2,6}', title)
    return [w for w in words if w not in STOP]


def agents_text():
    try:
        return open(AGENTS, encoding="utf-8").read()
    except Exception:
        return ''


def main():
    if not os.path.exists(DB):
        print("记忆库不存在:", DB)
        return
    c = sqlite3.connect(DB)
    rows = load_corrected(c)
    c.close()

    counter = Counter()
    for r in rows:
        for w in theme_of(r['title']):
            counter[w] += 1

    hot = [(k, v) for k, v in counter.most_common(40) if v >= 3]
    ag = agents_text()

    lines = []
    lines.append("# 记忆审计报告")
    lines.append("")
    lines.append("生成时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("")
    lines.append("## 总量")
    lines.append("- 用户纠正类记忆：**%d 条**" % len(rows))
    lines.append("- 主题词 ≥3 次（= 同一件事被纠正 3 遍以上）：**%d 个**" % len(hot))
    lines.append("")

    if hot:
        lines.append("## ⚠️ 反复被纠正的主题")
        lines.append("")
        lines.append("| 主题词 | 出现次数 | 已进 AGENTS.md 自检？ |")
        lines.append("|---|---|---|")
        for k, v in hot:
            lines.append("| %s | %d | %s |" % (k, v, "✅" if k in ag else "❌ 待处理"))
        lines.append("")
        missing = [k for k, v in hot if k not in ag]
        if missing:
            lines.append("**还没进自检的：%s**" % "、".join(missing))
            lines.append("")
            lines.append("> 处理方式：不要为它再记一条新教训。先把同类记忆合并成一条，")
            lines.append("> 再把可执行的动作写进 AGENTS.md「动手前 60 秒自检」。")
            lines.append("")

    lines.append("## importance=10 的纠正（最该守住）")
    lines.append("")
    for r in sorted(rows, key=lambda x: -x['imp'])[:12]:
        if r['imp'] >= 9:
            lines.append("- [%d] %s" % (r['imp'], r['title'][:70]))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 自我迭代口诀")
    lines.append("")
    lines.append("1. 同一件事被纠正 ≥3 次 → 它不是「记性不好」，是**机制没生效**")
    lines.append("2. 机制没生效的解法只有两个：**写进 AGENTS.md（每次加载）**，或**改成脚本/检查（自动执行）**")
    lines.append("3. 再记一条教训 = 下次还会犯")

    text = "\n".join(lines)
    try:
        open(OUT, "w", encoding="utf-8").write(text)
    except Exception as e:
        print("写报告失败:", e)
    if "--print" in sys.argv:
        print(text)
    else:
        print("报告已写:", OUT)
        print("反复被纠主题 %d 个，其中未进自检 %d 个" % (len(hot), len([k for k, v in hot if k not in ag])))


if __name__ == "__main__":
    main()
