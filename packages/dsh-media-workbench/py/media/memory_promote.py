# -*- coding: utf-8 -*-
"""记忆自我迭代：把「被反复纠正、但没进 AGENTS.md」的教训，自动晋升进自检区。

流程：
  1. 取所有带 corrected/用户纠正 标签的记忆标题
  2. 丢给 V3.2 做语义归并（同一件事换个说法也要认出来）
  3. 同一簇被纠正 >= 3 次 → 判为"机制没生效"
  4. 检查 AGENTS.md 里有没有这条（关键词匹配）
  5. 没有 → 生成一条可执行规则，追加进 AGENTS.md 的「自动晋升区」
  6. 改 AGENTS.md 前先备份

用法：
  python memory_promote.py          # 立刻跑
  python memory_promote.py --dry    # 只看会写什么，不动文件
  python memory_promote.py --if-due # 7 天内跑过就跳过（挂 DSH 启动用）
"""
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import urllib.request

DB = r"C:\Users\Administrator\.my-memory\memory.db"
AGENTS = r"E:\DSH-data\.dsh\AGENTS.md"
STAMP = r"E:\desktop\media\_promote_stamp.txt"
LOG = r"E:\desktop\media\_memory_promote.log"
BASE = "http://127.0.0.1:8326/v1"
KEYFILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
LEVELS = ("lesson", "rules", "fact", "project", "user", "topic", "soul")
MARK = "## 🔁 自动晋升区（memory_promote 维护，勿手改本节以下内容）"

if sys.stdout is None or sys.stderr is None:
    _n = open(os.devnull, "w")
    sys.stdout = sys.stdout or _n
    sys.stderr = sys.stderr or _n
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def api_key():
    try:
        return open(KEYFILE, encoding="utf-8").read().strip()
    except Exception:
        return ""


def due(days=7):
    try:
        last = float(open(STAMP, encoding="utf-8").read().strip())
        return (time.time() - last) > days * 86400
    except Exception:
        return True


def load_titles():
    c = sqlite3.connect(DB)
    out = []
    for lv in LEVELS:
        try:
            cur = c.execute(f"select title, tags from {lv}")
        except Exception:
            continue
        for title, tags in cur:
            tg = tags or ''
            if any(k in tg for k in ('corrected', '用户纠正', '用户要求', '用户强调')):
                if title:
                    out.append(title.strip())
    c.close()
    return out


def cluster(titles):
    """让 V3.2 把同一件事的不同说法归成一簇"""
    key = api_key()
    if not key:
        return []
    listing = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))
    prompt = (
        "下面是我被用户纠正过的记录标题（同一条规则常被写成不同措辞）。\n"
        "请把它们按「本质是同一个问题」归并成若干簇。只输出 JSON：\n"
        '{"clusters":[{"rule":"一句话说清这条规则该怎么做（祈使句，可执行）",'
        '"count":属于这簇的条数,"samples":["最多3个原始标题"]}]}\n'
        "只保留 count >= 3 的簇，按 count 从多到少排序。没有就返回 {\"clusters\":[]}。\n\n"
        + listing[:12000]
    )
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 3000,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            BASE + "/chat/completions", data=body,
            headers={"content-type": "application/json", "authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=240) as r:
            j = json.loads(r.read().decode("utf-8"))
        txt = j["choices"][0]["message"]["content"]
        m = re.search(r"\{[\s\S]*\}", txt)
        if not m:
            return []
        return json.loads(m.group(0)).get("clusters") or []
    except Exception as e:
        log("归并失败: %s" % e)
        return []


def already_in(text, rule):
    """粗判：这条规则的核心词是否已出现在 AGENTS.md 里"""
    if not text:
        return False
    words = [w for w in re.findall(r'[\u4e00-\u9fa5]{2,5}', rule)][:6]
    if not words:
        return False
    hit = sum(1 for w in words if w in text)
    return hit >= max(2, len(words) // 2)


def main():
    if "--if-due" in sys.argv and not due():
        return
    dry = "--dry" in sys.argv

    titles = load_titles()
    log("纠正类标题 %d 条" % len(titles))
    if not titles:
        return

    clusters = cluster(titles)
    log("归并出 %d 个 >=3 次的簇" % len(clusters))
    if not clusters:
        open(STAMP, "w", encoding="utf-8").write(str(time.time()))
        return

    try:
        ag = open(AGENTS, encoding="utf-8").read()
    except Exception:
        ag = ""

    todo = [c for c in clusters if c.get("rule") and not already_in(ag, c["rule"])]
    print("需要晋升的规则：%d 条" % len(todo))
    for c in todo:
        print("  [%dx] %s" % (c.get("count", 0), c["rule"][:70]))

    if not todo or dry:
        if dry and todo:
            print("\n（--dry，未写文件）")
        open(STAMP, "w", encoding="utf-8").write(str(time.time()))
        return

    # 备份
    try:
        shutil.copyfile(AGENTS, AGENTS + ".bak-promote-" + time.strftime("%Y%m%d_%H%M%S"))
    except Exception as e:
        log("备份失败，放弃写: %s" % e)
        return

    block = ["", MARK, ""]
    block.append("> 本节由 `E:\\desktop\\media\\memory_promote.py` 自动维护：")
    block.append("> 同一件事被用户纠正 ≥3 次、且 AGENTS.md 里原本没有 → 自动追加到这里。")
    block.append("> 手动改了这里的内容不影响下次运行（会去重）。")
    block.append("")
    for i, c in enumerate(todo, 1):
        n = c.get("count", 0)
        block.append("%d. **%s**　（被纠正 %d 次）" % (
            i, c["rule"].strip().rstrip("。"), n))
        for s in (c.get("samples") or [])[:2]:
            block.append("   - 当时的说法：%s" % str(s)[:60])
        block.append("")

    # 先删掉已有的「自动晋升区」章节，避免每次都追加出一个重复章节
    _marker = "## \U0001F501 自动晋升区"
    _pos = ag.find(_marker)
    if _pos > 0:
        ag = ag[:_pos].rstrip() + "\n"
    new = ag.rstrip() + "\n\n" + "\n".join(block) + "\n"
    try:
        open(AGENTS, "w", encoding="utf-8", newline="\n").write(new)
        log("已晋升 %d 条规则进 AGENTS.md" % len(todo))
        print("已写入 AGENTS.md（备份在 .bak-promote-*）")
    except Exception as e:
        log("写 AGENTS.md 失败: %s" % e)
        print("写失败:", e)

    open(STAMP, "w", encoding="utf-8").write(str(time.time()))


if __name__ == "__main__":
    main()
