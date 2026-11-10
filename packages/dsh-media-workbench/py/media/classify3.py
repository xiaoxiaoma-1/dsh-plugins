# -*- coding: utf-8 -*-
"""分类升级：8 大类 → 72 子类 + 三级主题标签（一书多标签）"""
import json, os, sqlite3, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
OUT = r"E:\desktop\media\_classify3.json"
BASE = "http://127.0.0.1:8326/v1"
KEY = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
MODEL = "siliconflow/deepseek-ai/DeepSeek-V3.2"

TREE = {
    "权谋与政治": ["权力法则", "博弈与算计", "谈判与较量", "人情往来", "面子与场合", "官场规则",
                   "汇报与向上", "识人与防人", "厚黑与暗面", "毛选原著", "毛选解读"],
    "商业与变现": ["搞钱思维", "副业接单", "创业生意", "投资理财", "定价", "销售成交", "文案报价",
                   "流量获取", "私域运营", "投放转化", "团队管理", "合伙股权", "招人用人",
                   "商业模式", "品牌定位", "商业史案例"],
    "内容创作": ["选题", "标题与开头", "结构与节奏", "平台规则", "起号与增长", "写作技法",
                 "故事与叙事", "视觉与设计", "短视频与直播"],
    "心理与人性": ["自我认知", "情绪管理", "关系处理", "欲望动机", "习惯养成", "认知偏差",
                   "人格性格", "创伤疗愈"],
    "语言与思维": ["表达与说服", "逻辑", "认知模型", "反常识", "思维工具", "决策判断",
                   "学习方法", "沟通技巧"],
    "AI 与工具": ["AI 用法", "提示词", "自动化", "效率工具"],
    "国学与哲学": ["心学", "道家与易", "儒家论语", "兵家孙子", "佛学与禅", "西方哲学",
                   "人生选择", "历史人物"],
    "身心与生活": ["身体健康", "睡眠", "运动", "冥想", "阅读", "时间管理", "极简整理", "生活方式"],
}
ALL_SUBS = {s for v in TREE.values() for s in v}
TREE_TXT = "\n".join("%s：%s" % (k, " / ".join(v)) for k, v in TREE.items())
TOTAL = len(ALL_SUBS)

SYS = "你是中文书籍分类与索引专家。只能从给定子类清单里选，绝不造子类；主题标签可以自由生成但必须具体。只输出 JSON。"
PROMPT = """书名：{title}
作者：{author}
正文节选：
{text}

【大类→子类清单】（子类只能从这里选，共 {total} 个）
{tree}

【任务】
1. topics：这本书属于哪几个大类？可多选，1-3 个。
2. subs：具体能挂哪些子类？**2-5 个**，必须来自上面清单，可跨大类。
3. tags：这本书**具体讲了什么**？3-6 个中文主题词，每个 2-8 字，不许用"人生""成长""思维"这类空词，要能一眼看出内容。例如《原子习惯》→ 习惯养成、行为设计、复利效应、环境设计、自我管理；《权力48条法则》→ 权力博弈、人性弱点、历史案例、自保策略。

只输出 JSON：
{{"topics":["大类1","大类2"],"subs":["子类1","子类2"],"tags":["标签1","标签2","标签3"],"why":"不超过20字"}}"""

_lock = threading.RLock()
_n = _tot = _fail = 0
_t0 = 0.0
res = {}


def call(title, author, text, tries=3):
    body = json.dumps({"model": MODEL, "temperature": 0.15, "max_tokens": 420,
                       "messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": PROMPT.format(
                                        title=title, author=author or "未知", text=text,
                                        total=TOTAL, tree=TREE_TXT)}]}).encode()
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
            topics = [x for x in (o.get("topics") or []) if x in TREE][:3]
            subs = [x for x in (o.get("subs") or []) if x in ALL_SUBS][:5]
            tags = []
            for t in (o.get("tags") or []):
                t = str(t).strip()
                if 2 <= len(t) <= 8 and t not in tags:
                    tags.append(t)
            tags = tags[:6]
            if not topics or not subs:
                raise ValueError("空分类")
            return {"topics": topics, "subs": subs, "tags": tags,
                    "why": str(o.get("why") or "")[:30]}
        except Exception:
            time.sleep(1 + i)
    return {"topics": [], "subs": [], "tags": [], "why": "失败"}


def work(row):
    global _n, _fail
    o = call(row[1], row[2], row[3])
    with _lock:
        _n += 1
        if not o["topics"]:
            _fail += 1
        res[row[0]] = o
        if _n % 100 == 0 or _n == _tot:
            print("  %d/%d | %.1f 分 | 失败 %d" % (_n, _tot, (time.time() - _t0) / 60, _fail), flush=True)
            dump()
    return row[0]


def dump():
    with _lock:
        snap = dict(res)
    tmp = OUT + ".tmp"
    json.dump(snap, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)


def main():
    global _tot, _t0
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 56
    c = sqlite3.connect(DB)
    rows = []
    for bid, t, a in c.execute("select id, title, coalesce(author,'') from books").fetchall():
        chs = c.execute("select content from book_chunks where book_id=? order by page_from limit 5",
                        (bid,)).fetchall()
        rows.append((bid, t, a, "\n…\n".join((x[0] or "")[:520] for x in chs)[:2400]))
    c.close()
    _tot = len(rows)
    _t0 = time.time()
    print("待分类 %d 本｜%d 个子类｜并发 %d" % (_tot, TOTAL, workers), flush=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, rows))
    dump()

    c = sqlite3.connect(DB)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    c.execute("drop table if exists book_classify")
    c.execute("""create table book_classify(
        book_id text primary key, topics text, subs text, tags text, why text, created_at text)""")
    for bid, o in res.items():
        c.execute("insert or replace into book_classify values(?,?,?,?,?,?)",
                  (bid, ",".join(o["topics"]), ",".join(o["subs"]), ",".join(o["tags"]), o["why"], now))
    c.commit()
    c.close()

    from collections import Counter
    ok = [o for o in res.values() if o["topics"]]
    print("\n完成 %d｜失败 %d｜%.1f 分" % (len(res), _fail, (time.time() - _t0) / 60))
    print("大类分布:", Counter(x for o in ok for x in o["topics"]).most_common())
    print("子类覆盖:", len({s for o in ok for s in o["subs"]}), "/", TOTAL)
    print("标签总数:", len({t for o in ok for t in o["tags"]}))
    print("平均每本子类 %.1f 个 / 标签 %.1f 个" % (
        sum(len(o["subs"]) for o in ok) / max(1, len(ok)),
        sum(len(o["tags"]) for o in ok) / max(1, len(ok))))


if __name__ == "__main__":
    main()
