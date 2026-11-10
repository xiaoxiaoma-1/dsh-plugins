# -*- coding: utf-8 -*-
"""仓颉阶段1：5 个提取器并行提取候选方法论单元"""
import json, os, re, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
BOOK = sys.argv[1] if len(sys.argv) > 1 else "内容创作"
SRC = r"E:\desktop\书库盘点\_cangjie_input\%s.md" % BOOK.replace("/", "_")
OUT = r"E:\desktop\书库盘点\cangjie\books\content-creation\candidates"
os.makedirs(OUT, exist_ok=True)
CHUNK = 12000
OVERLAP = 600

SYS = "你是方法论提取器。只从给定的原文里提取，不脑补、不总结成空话。只输出 JSON。"

EXTRACTORS = {
    "framework": """以下是《{book}》的正文片段。

任务：提取**可执行的框架/流程/模型**——即"先做什么、再做什么、什么时候停"的结构化做法。

只要满足以下任一条就算：
- 一个有明确步骤的流程（≥3 步，步骤有先后依赖）
- 一个决策模型（什么条件下选 A，什么条件下选 B）
- 一个排查/诊断路径（出现某现象，按什么顺序找原因）

不要提取：泛泛的道理、作者的态度、书评式总结、单纯的概念解释。

输出 JSON 数组，每项：
{{"name":"框架名（≤12字）","goal":"解决什么问题（≤30字）","steps":["步骤1","步骤2","步骤3"],"cond":"适用条件/什么时候用（≤30字）","src":"原文出处（书名或章节，有就写，没有写null）","quote":"支撑它的原文一句（≤60字，必须是原文）"}}

最多 6 项，宁缺毋滥。没有就输出 []。

原文片段：
{text}""",

    "principle": """以下是《{book}》的正文片段。

任务：提取**原则/规则/清单/计算口径**——即"必须这样做、不许那样做"或"按这个标准算"的硬性规定。

只要满足以下任一条就算：
- 一条带判断标准的规则（含数字、比例、阈值、排序优先级的优先）
- 一份检查清单（做之前或做之后要逐条对的东西）
- 一个计算公式或量化口径

不要提取：价值观、励志口号、对行业的主观评价。

输出 JSON 数组，每项：
{{"name":"原则名（≤12字）","rule":"规则原文式表述（≤50字）","why":"为什么成立（≤30字，没有就写null）","num":"涉及的数字/阈值（没有写null）","src":"出处或null","quote":"原文一句（≤60字，必须是原文）"}}

最多 6 项，宁缺毋滥。没有就输出 []。

原文片段：
{text}""",

    "case": """以下是《{book}》的正文片段。

任务：提取**具体案例**——书里真实发生过的、可复述的事件或数据。

只要满足以下任一条就算：
- 一个有具体主体（公司/人/品牌/产品）和具体结果的事件
- 一组带来源的数据（多少、比例、增长了几倍）
- 一次 A/B 对照或前后对比

不要提取：作者假设的例子、如果式的推演、没有主体的空泛举例。

输出 JSON 数组，每项：
{{"name":"案例名（≤14字）","who":"主体","what":"做了什么（≤40字）","result":"结果/数据（≤40字）","lesson":"能说明什么（≤30字）","src":"出处或null","quote":"原文一句（≤60字）"}}

最多 6 项。没有就输出 []。

原文片段：
{text}""",

    "counter": """以下是《{book}》的正文片段。

任务：提取**反例/失败模式**——书里明确警告"这样做会失败"的地方。

只要满足以下任一条就算：
- 明确点名的错误做法（"不要…""最忌讳…""这样做等于…"）
- 一个失败案例及其原因
- 一个常见误判/误区

不要提取：作者的谦虚话、免责声明、对同行的暗讽。

输出 JSON 数组，每项：
{{"name":"失败模式名（≤12字）","wrong":"错在哪（≤40字）","cost":"代价是什么（≤30字）","avoid":"怎么避免（≤40字）","src":"出处或null","quote":"原文一句（≤60字）"}}

最多 6 项。没有就输出 []。

原文片段：
{text}""",

    "glossary": """以下是《{book}》的正文片段。

任务：提取**关键术语/概念**——书里反复用、且有特定含义的词。

只要满足以下任一条就算：
- 一个行业黑话或专业术语，外行看不懂
- 一个作者自定义的概念
- 一个被误用的常见词，书里给了正解

不要提取：普通词汇、人名、书名。

输出 JSON 数组，每项：
{{"term":"术语","def":"书里给的定义或用法（≤40字）","why":"为什么要懂它（≤30字）","quote":"原文一句（≤50字）"}}

最多 8 项。没有就输出 []。

原文片段：
{text}""",
}

_lock = threading.RLock()
done = 0
total = 0
t0 = time.time()
fail = 0
pool = {k: [] for k in EXTRACTORS}


def call(kind, text, tries=2):
    body = json.dumps({"model": MODEL, "temperature": 0.2, "max_tokens": 1600,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": EXTRACTORS[kind].format(book=BOOK, text=text)}]}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.load(r)
            s = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            s = s[s.find("["): s.rfind("]") + 1]
            arr = json.loads(s)
            return [x for x in arr if isinstance(x, dict)][:8]
        except Exception:
            time.sleep(1 + i)
    return None


def work(task):
    global done, fail
    kind, idx, text = task
    r = call(kind, text)
    with _lock:
        done += 1
        if r is None:
            fail += 1
        else:
            pool[kind].extend(r)
        if done % 20 == 0:
            print("  %d/%d | %.1f 分 | 失败 %d" % (done, total, (time.time() - t0) / 60, fail), flush=True)
    return 1


def main():
    global total
    raw = open(SRC, encoding="utf-8").read()
    # 按子类切，保持语义完整
    chunks, cur = [], ""
    for para in raw.split("\n\n"):
        if len(cur) + len(para) > CHUNK and cur:
            chunks.append(cur)
            cur = cur[-OVERLAP:] + "\n\n" + para
        else:
            cur += ("\n\n" if cur else "") + para
    if cur:
        chunks.append(cur)
    print("《%s》%d 字 → %d 块 × %d 个提取器 = %d 次调用" % (BOOK, len(raw), len(chunks), len(EXTRACTORS),
                                                     len(chunks) * len(EXTRACTORS)))
    tasks = [(k, i, c) for k in EXTRACTORS for i, c in enumerate(chunks)]
    total = len(tasks)
    with ThreadPoolExecutor(max_workers=40) as ex:
        list(ex.map(work, tasks))

    # 去重（同名合并）
    names = {
        "framework": ("name", "框架"), "principle": ("name", "原则"),
        "case": ("name", "案例"), "counter": ("name", "失败模式"), "glossary": ("term", "术语"),
    }
    for kind, items in pool.items():
        key, cn = names[kind]
        seen, uniq = set(), []
        for x in items:
            n = (x.get(key) or "").strip()
            if not n or n in seen:
                continue
            seen.add(n)
            uniq.append(x)
        pool[kind] = uniq
        fn = os.path.join(OUT, "%s.md" % kind)
        with open(fn, "w", encoding="utf-8") as f:
            f.write("# 候选池：%s（%s）\n\n来源：《%s》大类汇编\n\n" % (cn, kind, BOOK))
            for i, x in enumerate(uniq, 1):
                f.write("## %d. %s\n\n" % (i, x.get(key, "")))
                for k, v in x.items():
                    if k != key and v:
                        f.write("- **%s**: %s\n" % (k, v))
                f.write("\n")
        print("%-10s 候选 %d 条 → %s" % (cn, len(uniq), os.path.basename(fn)))

    print("\n完成 %.1f 分 | 失败 %d 次调用" % ((time.time() - t0) / 60, fail))


if __name__ == "__main__":
    main()
