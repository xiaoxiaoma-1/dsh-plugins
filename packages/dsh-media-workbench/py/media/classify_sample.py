"""
稿库分类 · 50 条小样试跑（V3.2 走本机网关）

只读不写库：结果落 jsonl，人抽检后再决定全量。
用法：python classify_sample.py [条数]
产物：E:\desktop\media\_classify_sample.jsonl
"""
import json
import os
import random
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")

DB = r"E:\desktop\media\workbench.db"
OUT = r"E:\desktop\media\_classify_sample.jsonl"
BASE = "http://127.0.0.1:8326/v1"
KEY_FILE = r"E:\DSH-data\.dsh\openai-gateway\api-key"
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

TREE = {
    "权谋与政治": ["权力与博弈", "人情世故", "体制与生存", "毛选"],
    "商业与变现": ["搞钱路径", "定价与成交", "流量获客", "团队与合伙"],
    "内容创作": ["选题", "标题与开头", "结构与节奏", "平台规则", "起号与增长"],
    "心理与人性": ["自我认知", "情绪", "关系", "欲望与动机"],
    "语言与思维": ["表达与说服", "逻辑", "认知模型", "反常识"],
    "AI 与工具": ["AI 用法", "提示词", "自动化", "效率工具"],
    "国学与哲学": ["心学", "道家与易", "人生选择", "历史人物"],
    "身心与生活": ["身体", "冥想", "阅读", "生活方式"],
}
ALL_SUBS = [s for v in TREE.values() for s in v]

SYS = "你是中文内容分类器。只能从给定的大类和子类清单里选，绝不自己造词。只输出 JSON，不要解释。"

def build_user(kind, author, text):
    lines = []
    for d, subs in TREE.items():
        lines.append(f"{d}：{' / '.join(subs)}")
    tree_txt = "\n".join(lines)
    return f"""来源：{kind}｜作者：{author or '未知'}
正文：
{text[:1200]}

【大类清单】
{chr(10).join(TREE.keys())}

【子类清单（必须属于你选的大类）】
{tree_txt}

判断这段内容主要在讲什么，输出 JSON：
{{"d1":"大类1","d2":"第二个大类或 null","subs":["子类1"],"conf":0.0-1.0,"why":"20字内理由"}}

要求：
- d1 必填且必须在 8 个大类里；d2 只有明显跨两个大类才填，否则 null
- subs 取 1-2 个，必须属于 d1 或 d2，用清单里的原词
- 讲的是"怎么做/怎么赚钱/怎么说话"这类方法，就归方法所在的大类，不要归到"语言与思维"
- conf 表示你自己的把握"""


def call(messages, max_tokens=900, timeout=120):
    key = open(KEY_FILE, encoding="utf-8").read().strip()
    body = json.dumps({
        "model": MODEL, "temperature": 0.2, "max_tokens": max_tokens,
        "messages": messages,
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def pick(limit):
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    cur = c.cursor()
    plan = [("主贴", 20), ("引用", 5), ("douyin", 15), ("live", 10)]
    rows = []
    for kind, n in plan:
        got = cur.execute(
            "select id, kind, author, date, text from posts "
            "where kind=? and coalesce(text,'')<>'' order by random() limit ?", (kind, n)).fetchall()
        rows += [dict(r) for r in got]
    random.shuffle(rows)
    c.close()
    return rows[:limit]


def one(item, idx, total):
    t0 = time.time()
    try:
        j = call([
            {"role": "system", "content": SYS},
            {"role": "user", "content": build_user(item["kind"], item["author"], item["text"])},
        ])
        content = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        usage = j.get("usage") or {}
        ok, err = True, None
        d1 = d2 = None
        subs, conf, why = [], None, ""
        try:
            s = content.strip()
            if s.startswith("```"):
                s = s.split("```")[1]
                s = s[s.find("{"):]
            obj = json.loads(s[s.find("{"): s.rfind("}") + 1])
            d1 = obj.get("d1")
            d2 = obj.get("d2")
            subs = [x for x in (obj.get("subs") or []) if isinstance(x, str)]
            conf = obj.get("conf")
            why = obj.get("why") or ""
            if d1 not in TREE:
                ok, err = False, "大类不在清单：" + str(d1)
            bad = [x for x in subs if x not in ALL_SUBS]
            if bad:
                ok, err = False, "自造子类：" + ",".join(bad)
            if d2 and d2 not in TREE:
                d2 = None
        except Exception as e:
            ok, err = False, "解析失败：" + str(e)[:60]
        rec = {
            "idx": idx, "id": item["id"], "kind": item["kind"], "author": item["author"],
            "chars": len(item["text"] or ""), "d1": d1, "d2": d2, "subs": subs,
            "conf": conf, "why": why, "ok": ok, "err": err,
            "tokens_in": usage.get("prompt_tokens"), "tokens_out": usage.get("completion_tokens"),
            "sec": round(time.time() - t0, 1),
            "head": (item["text"] or "")[:80].replace("\n", " "),
        }
    except Exception as e:
        rec = {"idx": idx, "id": item["id"], "kind": item["kind"], "author": item["author"],
               "chars": len(item["text"] or ""), "ok": False, "err": "请求失败：" + str(e)[:80],
               "sec": round(time.time() - t0, 1), "head": (item["text"] or "")[:80].replace("\n", " ")}
    print(f"[{idx}/{total}] {rec.get('kind')} {rec.get('d1')} / {rec.get('subs')} "
          f"conf={rec.get('conf')} {rec.get('sec')}s {rec.get('err') or ''}", flush=True)
    return rec


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    rows = pick(limit)
    print(f"取 {len(rows)} 条：", {k: sum(1 for r in rows if r["kind"] == k) for k in {r["kind"] for r in rows}})
    t0 = time.time()
    out = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(one, it, i + 1, len(rows)) for i, it in enumerate(rows)]
        for f in futs:
            out.append(f.result())
    with open(OUT, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    okn = sum(1 for r in out if r.get("ok"))
    tin = sum(r.get("tokens_in") or 0 for r in out)
    tout = sum(r.get("tokens_out") or 0 for r in out)
    print(f"\n完成：{okn}/{len(out)} 条格式合法，用时 {time.time()-t0:.0f}s")
    print(f"token：输入 {tin:,} / 输出 {tout:,} / 条均 {(tin+tout)/max(len(out),1):.0f}")
    from collections import Counter
    print("大类分布：", Counter(r.get("d1") for r in out).most_common())
    print("失败原因：", Counter(r.get("err") for r in out if not r.get("ok")).most_common(5))
    print("产物：", OUT)


if __name__ == "__main__":
    main()
