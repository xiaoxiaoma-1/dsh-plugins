# -*- coding: utf-8 -*-
"""给内容库里「未分类」的稿子自动归类。

规则：按关键词命中数打分，取最高的一类写进 posts.topic_override。
已经有 topic_override、有原子（会被 atoms 的话题覆盖）、是书籍（kind=book）的都不动。

用法：
  python classify.py            # 处理所有待归类的
  python classify.py --all      # 覆盖重算所有非书籍稿
  python classify.py --dry      # 只打印不写库
"""
import sqlite3
import sys

DB = r"E:\desktop\media\workbench.db"

KW = {
    "商业模式与定价": ["商业模式", "定价", "赚钱", "生意", "利润", "变现", "客户", "收入", "成本",
                    "价格", "付费", "成交", "毛利", "销售", "客单", "复购"],
    "内容创作与平台": ["小红书", "抖音", "视频号", "公众号", "推特", "账号", "内容", "流量", "粉丝",
                    "爆款", "平台", "起号", "推文", "博主", "IP", "选题", "播放", "点赞"],
    "AI与工具": ["AI", "模型", "GPT", "prompt", "agent", "智能体", "skill", "工具", "代码", "编程",
               "notion", "obsidian", "飞书", "自动化", "token", "claude", "gpt"],
    "人生哲学与价值观": ["人生", "意义", "价值", "选择", "自由", "命运", "世界", "哲学", "死亡", "幸福"],
    "语言与思维": ["语言", "表达", "思维", "逻辑", "概念", "定义", "思考", "写作", "文字", "沟通"],
    "心理与执行力": ["执行", "拖延", "习惯", "情绪", "焦虑", "自控", "坚持", "行动", "自律", "目标", "沉迷"],
    "对标与模仿": ["对标", "模仿", "抄", "参考", "benchmark", "跟随"],
    "知识付费与教育": ["课程", "学员", "教学", "知识付费", "训练营", "咨询", "答疑", "私教", "陪跑", "上课"],
    "中国市场与下沉": ["中国", "下沉", "县城", "三四线", "国内"],
    "案例与实战复盘": ["复盘", "案例", "总结", "数据", "结果", "测试", "实验", "验证"],
}


def classify(text):
    best, score = None, 0
    for topic, kws in KW.items():
        s = sum(text.count(k) for k in kws)
        if s > score:
            best, score = topic, s
    return best


def main():
    dry = "--dry" in sys.argv
    force = "--all" in sys.argv
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    # 只处理「没有原子」的稿子：有原子的稿子话题由 atoms.topics 决定，比关键词准
    cond = ("coalesce(hidden,0)=0 and kind!='book' "
            "and not exists (select 1 from atoms a where a.url=posts.url)")
    if not force:
        cond += " and coalesce(topic_override,'')=''"
    rows = con.execute(f"select id, text, kind from posts where {cond}").fetchall()
    n = 0
    for r in rows:
        t = classify(r["text"] or "")
        if not t:
            continue
        n += 1
        if dry:
            print(f"  {t} <- {(r['text'] or '')[:50]!r}")
        else:
            con.execute("update posts set topic_override=? where id=?", (t, r["id"]))
    if not dry:
        con.commit()
    left = con.execute(f"""select count(*) from posts where {cond}""").fetchone()[0]
    print(f"[classify] 处理 {n} 条 | 待归类 {len(rows)} -> 剩余 {left if not dry else len(rows)-n}")
    con.close()


if __name__ == "__main__":
    main()
