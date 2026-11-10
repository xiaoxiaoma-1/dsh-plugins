# -*- coding: utf-8 -*-
"""清理 AGENTS.md 里重复的旧 footer（版本 1.4 那段）。"""
import io
import re
import os

p = os.path.expanduser(r"~\.dsh\AGENTS.md")
t = io.open(p, encoding="utf-8").read()

before = t.count("版本：1.4")
# 删掉「--- + 全局基准配置 + 版本1.4 + 最后更新」整段（含尾部空行）
pat = re.compile(r"---\s*\n\s*\*全局基准配置\*\s*\n\s*\*版本：1\.4\*\s*\n\s*\*最后更新：2026-10-30[^\n]*\n*", re.S)
t2, n = pat.subn("", t)

io.open(p, "w", encoding="utf-8", newline="\n").write(t2)
print("替换段数:", n, "| 1.4 之前:", before, "之后:", t2.count("版本：1.4"))
print("末尾 120 字:")
print(t2[-160:])
