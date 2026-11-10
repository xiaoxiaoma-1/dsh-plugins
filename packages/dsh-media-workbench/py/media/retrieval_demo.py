# -*- coding: utf-8 -*-
"""实测检索：拿「普通人怎么攒第一桶金」从库里捞真素材（两段式：召回 + 精排）"""
import json, sqlite3, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

# 第一桶金的真实语义，扩成短语集
PHRASES = ["第 一 桶 金", "启 动 资 金", "本 金", "原 始 积 累", "攒 钱", "存 钱",
           "储 蓄", "白 手 起 家", "从 零 开 始", "小 成 本", "轻 资 产", "副 业",
           "赚 到 第 一", "第 一 笔", "积 累 资 金", "没 有 本 钱", "月 薪", "攒 下"]
EXPR = " OR ".join('"%s"' % p for p in PHRASES)

c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()

print("=== 第一步：召回（按 18 个相关短语在大类过滤后的范围里搜）===")
cands = []
for topic in ["商业与变现", "内容创作", "心理与人性", "权谋与政治", "语言与思维"]:
    rows = q("""select f.book_id, b.title, f.page_from, f.content,
                       bc.topics, bc.subs, bc.tags
                from chunks_fts f
                join book_classify bc on bc.book_id=f.book_id
                join books b on b.id=f.book_id
                where f.tok match ? and bc.topics like ?
                limit 120""", (EXPR, "%" + topic + "%"))
    for bid, title, pf, content, topics, subs, tags in rows:
        cands.append({"src": "书", "title": title, "page": pf, "text": content or "",
                      "topic": topic, "subs": subs, "tags": tags})
    print("   %-8s 召回 %d 段" % (topic, len(rows)))

# 文案
for topic in ["商业与变现", "内容创作", "心理与人性"]:
    rows = q("""select p.id, coalesce(p.author,''), p.text, pc.subs, pc.tags
                from posts p join post_classify pc on pc.src_id='post:'||p.id
                where pc.topics like ? and (p.text like '%第一桶金%' or p.text like '%本金%'
                      or p.text like '%攒钱%' or p.text like '%存钱%' or p.text like '%启动资金%'
                      or p.text like '%副业%' or p.text like '%白手起家%')
                limit 80""", ("%" + topic + "%",))
    for pid, author, text, subs, tags in rows:
        cands.append({"src": "文案", "title": "@" + (author or "抖音"), "page": 0,
                      "text": text or "", "topic": topic, "subs": subs, "tags": tags})
    print("   %-8s 文案召回 %d 条" % (topic, len(rows)))

# 粗筛：长度合适、含具体信息（数字/步骤感）
def rough(x):
    t = x["text"]
    if len(t) < 120 or len(t) > 3000:
        return False
    nums = sum(ch.isdigit() for ch in t)
    x["nums"] = nums
    return nums >= 2 or "第一步" in t or "方法" in t or "做法" in t

cands = [x for x in cands if rough(x)]
# 去重
seen, uniq = set(), []
for x in cands:
    k = x["text"][:60]
    if k in seen:
        continue
    seen.add(k)
    uniq.append(x)
uniq.sort(key=lambda x: -x["nums"])
print("   去重粗筛后 %d 段" % len(uniq))
c.close()

# ===== 第二步：精排（V3.2 判能不能直接写进稿子）=====
SYS = "你是内容编辑。判断一段素材能不能直接用进一篇讲'普通人怎么攒第一桶金'的稿子。只输出 JSON。"
PROMPT = """目标：写一篇《普通人怎么攒第一桶金》的稿子，读者是普通上班族。

这段素材：
{text}

判断三件事：
1. concrete：它给的是**具体的东西**（方法、步骤、数字、真实案例、说话），还是空道理？
2. useful：普通人看了能不能照着做，或者至少改变一个认知？
3. quotable：这段话里有没有一句能直接写进稿子的原话？（有就摘出来，没有填 null）

只输出 JSON：
{{"concrete":true|false,"useful":true|false,"quotable":"一句原话或null","score":0-10,"why":"不超过20字"}}"""

_lock = threading.RLock()
res = {}


def judge(i_x):
    i, x = i_x
    body = json.dumps({"model": MODEL, "temperature": 0.1, "max_tokens": 240,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(text=x["text"][:1200])}]}).encode()
    for t in range(2):
        try:
            req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=90) as r:
                j = json.load(r)
            s = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            s = s[s.find("{"): s.rfind("}") + 1]
            o = json.loads(s)
            with _lock:
                res[i] = o
            return 1
        except Exception:
            time.sleep(1)
    with _lock:
        res[i] = {"score": 0}
    return 0


pool = uniq[:90]
print("\n=== 第二步：V3.2 精排 %d 段 ===" % len(pool))
t0 = time.time()
with ThreadPoolExecutor(max_workers=30) as ex:
    list(ex.map(judge, list(enumerate(pool))))
print("   完成 %.1f 分" % ((time.time() - t0) / 60))

scored = []
for i, x in enumerate(pool):
    o = res.get(i) or {}
    if o.get("concrete") and o.get("useful"):
        x["score"] = o.get("score", 0)
        x["quotable"] = o.get("quotable")
        x["why"] = o.get("why", "")
        scored.append(x)
scored.sort(key=lambda x: -x["score"])
print("   可用素材 %d 段（concrete+useful 双过）" % len(scored))

out = ["=== 「普通人怎么攒第一桶金」检索结果（前 20 段）===\n"]
for i, x in enumerate(scored[:20], 1):
    out.append("\n%d. 【%s】%s" % (i, x["src"], x["title"][:44]))
    out.append("   分类：%s / %s" % (x["topic"], x["subs"]))
    if x["src"] == "书":
        out.append("   位置：第 %s 页" % x["page"])
    out.append("   原文：%s" % x["text"][:700].replace("\n", " "))
    if x.get("quotable"):
        out.append("   ★ 可写进稿子的一句：%s" % x["quotable"])
    out.append("   （评分 %s｜%s）" % (x.get("score"), x.get("why")))
open(r"E:\desktop\media\_retrieval_demo.txt", "w", encoding="utf-8").write("\n".join(out))
json.dump(scored[:20], open(r"E:\desktop\media\_retrieval_demo.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("已写 _retrieval_demo.txt")
