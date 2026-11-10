# -*- coding: utf-8 -*-
"""仓颉阶段1.5：三重验证 + 按「自媒体写稿」场景筛掉不可迁移项"""
import json, os, re, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"
CDIR = r"E:\desktop\书库盘点\cangjie\books\content-creation"
OUT = r"E:\desktop\书库盘点\_verify15.json"

SYS = "你是方法论审计员。按三重验证 + 场景适配判一条候选，只输出 JSON。"

PROMPT = """候选方法论单元（从《内容创作》大类 148 本书提炼）：
类型：{kind}
名称：{name}
内容：{body}
原文引用：{quote}

【使用者的真实场景】
自媒体作者，一个人写稿：有一个主题和一堆素材，要写出能直接发布的内容。他不是广告公司，不拍片、不管团队、不做投放、不接客户需求。凡是需要团队协作、拍摄、客户沟通、预算投放才能用的方法，对他无效。

【三重验证，逐条判】
V1 来源充分性：上面「原文引用」是真原文、并且足以支撑这个说法吗？（引用为空、或引用与该说法无关 → false）
V2 可执行性：换一个新的主题和素材，他能照着做出来、并且能自己核验结果吗？（只是"要用心""要有创意"这种无法核验的 → false）
V3 任务增益：对「写出一篇能发的稿子」这件事有实际帮助吗？还是只是行业知识/流程/概念？（帮不上 → false）

【判定】
- verified：三条全 true
- reference：V1 过、但主要当背景知识参考（V2 或 V3 有一条 false）
- needs_review：原文引用可疑，需要回原文核对
- rejected：不满足 V1，或是团队/拍摄/投放流程，对单人写稿无意义

只输出 JSON：
{{"v1":true|false,"v2":true|false,"v3":true|false,"verdict":"verified|reference|needs_review|rejected","why":"不超过30字","keep":"如果 verified，会用它做什么（不超过25字）"}}"""

_lock = threading.RLock()
done = total = fail = 0
t0 = time.time()
res = {}


def parse_md(path, kind):
    items = []
    txt = open(path, encoding="utf-8").read()
    cur = None
    for ln in txt.split("\n"):
        m = re.match(r"^## \d+\. (.+)$", ln.strip())
        if m:
            if cur:
                items.append(cur)
            cur = {"name": m.group(1).strip(), "kind": kind, "body": [], "quote": ""}
            continue
        m2 = re.match(r"^- \*\*(.+?)\*\*: (.*)$", ln.strip())
        if m2 and cur:
            k, v = m2.group(1), m2.group(2).strip()
            if k in ("quote", "term"):
                cur["quote"] = v
            if k != "quote":
                cur["body"].append("%s：%s" % (k, v))
    if cur:
        items.append(cur)
    for x in items:
        x["body"] = "｜".join(x["body"])[:600]
    return items


def call(item, tries=2):
    body = json.dumps({"model": MODEL, "temperature": 0.1, "max_tokens": 260,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(
                                        kind=item["kind"], name=item["name"],
                                        body=item["body"], quote=item["quote"] or "（无）")}]}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=90) as r:
                j = json.load(r)
            s = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            s = s[s.find("{"): s.rfind("}") + 1]
            o = json.loads(s)
            v = (o.get("verdict") or "").strip()
            if v not in ("verified", "reference", "needs_review", "rejected"):
                raise ValueError("bad verdict")
            return {"v1": bool(o.get("v1")), "v2": bool(o.get("v2")), "v3": bool(o.get("v3")),
                    "verdict": v, "why": str(o.get("why") or "")[:40],
                    "keep": str(o.get("keep") or "")[:30]}
        except Exception:
            time.sleep(1 + i)
    return None


def work(item):
    global done, fail
    o = call(item)
    with _lock:
        done += 1
        if o is None:
            fail += 1
        else:
            res[item["name"] + "|" + item["kind"]] = dict(item, **o)
        if done % 100 == 0:
            print("  %d/%d | %.1f 分 | 失败 %d" % (done, total, (time.time() - t0) / 60, fail), flush=True)
    return 1


def main():
    global total
    kinds = {"framework": "框架", "principle": "原则", "case": "案例",
             "counter": "失败模式", "glossary": "术语"}
    items = []
    for k, cn in kinds.items():
        p = os.path.join(CDIR, "candidates", k + ".md")
        if os.path.exists(p):
            got = parse_md(p, cn)
            items.extend(got)
            print("  %s 解析 %d 条" % (cn, len(got)))
    total = len(items)
    print("共 %d 条待验证，40 并发" % total, flush=True)
    with ThreadPoolExecutor(max_workers=40) as ex:
        list(ex.map(work, items))
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    from collections import Counter
    cnt = Counter(v["verdict"] for v in res.values())
    print("\n=== 三重验证结果 ===")
    for k in ("verified", "reference", "needs_review", "rejected"):
        print("   %-12s %d" % (k, cnt[k]))
    print("   按类型：")
    for k in ("verified", "reference", "needs_review", "rejected"):
        sub = Counter(v["kind"] for v in res.values() if v["verdict"] == k)
        print("      %-12s %s" % (k, dict(sub)))
    print("\n=== verified 样例（前 12 条）===")
    n = 0
    for v in res.values():
        if v["verdict"] == "verified":
            print("   [%s] %s —— %s" % (v["kind"], v["name"], v["keep"]))
            n += 1
            if n >= 12:
                break
    print("\n完成 %.1f 分" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
