# -*- coding: utf-8 -*-
"""从抖音私信 HTML 里提取跟视频卡片相关的片段，给 V3.2 分析"""
import json, re, sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"E:\desktop\media\_douyin_chat.html"
html = open(p, encoding="utf-8", errors="ignore").read()
print("HTML 长度:", len(html))

out = []
# 1. 找所有 class 名里带关键词的
classes = set()
for m in re.finditer(r'class="([^"]{1,200})"', html):
    for c in m.group(1).split():
        if re.search(r"message|msg|chat|bubble|share|aweme|video|card", c, re.I):
            classes.add(c)
print("相关 class 名:", len(classes))
for c in sorted(classes)[:40]:
    out.append("CLASS: " + c)

# 2. 找 aweme / itemId / videoId 相关的键值
for kw in ["aweme_id", "awemeId", "itemId", "item_id", "video_id", "vid"]:
    for m in re.finditer(re.escape(kw) + r'["\']?\s*[:=]\s*["\']?(\d{10,25})', html):
        out.append("KEY %s = %s" % (kw, m.group(1)))
        break

# 3. 找所有 19-20 位数字，记录它们的上下文
nums = {}
for m in re.finditer(r"\b(\d{19})\b", html):
    n = m.group(1)
    if n not in nums:
        s = max(0, m.start() - 120)
        nums[n] = html[s:m.end() + 40].replace("\n", " ")[-180:]
out.append("\n=== 19位数字（前15个，带上下文）===")
for i, (n, ctx) in enumerate(list(nums.items())[:15], 1):
    out.append("%2d. %s\n    %s" % (i, n, ctx))

# 4. 找含"视频"字样的元素片段
out.append("\n=== 含「视频」的片段（前8个）===")
for i, m in enumerate(re.finditer("视频", html), 1):
    s = max(0, m.start() - 250)
    seg = html[s:m.end() + 150].replace("\n", " ")
    out.append("%d. ...%s..." % (i, seg[-380:]))
    if i >= 8:
        break

txt = "\n".join(out)
open(r"E:\desktop\media\_douyin_frag.txt", "w", encoding="utf-8").write(txt)
print("片段已写 _douyin_frag.txt，长度:", len(txt))

# 给 V3.2 的输入控制在 12000 字内
short = txt[:12000]
open(r"E:\desktop\media\_douyin_frag_small.txt", "w", encoding="utf-8").write(short)
print("送 V3.2 的版本:", len(short), "字")
