# -*- coding: utf-8 -*-
"""把热点 JSON 里的英文补上中文译文（title_zh / text_zh）。

设计：
- 以英文原文为 key 的翻译表（TH），命中就写入 *_zh 字段，未命中保留原文。
- 可反复运行，幂等。
- 用途：由 AI 维护 TH，或由上层（定时任务）生成后写回。

用法：python hot_i18n.py [json路径]
"""
import json
import os
import sys

DEFAULT_JSON = r"E:\desktop\hot\hot-2026-10-30.json"

TH = {
    # ---------- Hacker News ----------
    "Patrick Stewart has died": "帕特里克·斯图尔特去世",
    "We're releasing the weights of Mistral Large 4": "Mistral 开源 Large 4 的模型权重",
    "Binance-hacker-1029 – $5.6B stolen from Binance": "币安被盗 56 亿美元",
    "DoorDash to acquire Instacart": "DoorDash 宣布收购 Instacart",
    "LLM Voice": "大模型的「声音」",
    "H.264 Is Magic (2016)": "H.264 是个魔术（2016 年旧文）",
    "Chained PHP2Shell exploit roots 25 servers, including US Government servers": "PHP2Shell 链式漏洞拿下 25 台服务器，含美国政府机器",
    "If IPv4 were land": "如果 IPv4 是一块块土地",
    "We ran AI agent swarms in Minecraft and Mindustry": "我们在《我的世界》和《异星工厂》里跑 AI 智能体集群",
    "Grace Blackwell needs a new scheduler: 27% more usable GPUs from the same racks": "Grace Blackwell 需要新调度器：同一机架多出 27% 可用 GPU",

    # ---------- AI ----------
    "⚡Iterating at lightning speed! Gemini 4 Carbon is SOTA across key benchmarks and combines frontier capabilities with deep safety &amp; security research.":
        "迭代快得惊人。Gemini 4 Carbon 在关键基准上全面领先，把前沿能力和深度安全研究绑在了一起。",
    "We’ve expanded our AI for Science program beyond individual teams to support some of the world’s leading scientific foundations, institutions, and research groups.":
        "我们把「AI for Science」计划从单个团队扩展到全球顶级科研基金会、机构和研究组。",

    # ---------- 商业 ----------
    "I got so involved in an idea I was talking about with Sorin Lerner that I literally fell off my chair. Though honestly it was a pretty badly designed chair...":
        "我跟 Sorin Lerner 聊一个想法聊得太投入，直接从椅子上摔下来了。不过说实话那把椅子设计得也确实够烂……",
    "If you aren't stressed AF running your startup today, something is wrong\n\nBut also\n\nIf you aren't having the best time building ever, in your entire career in software ...\n\nSomething is wrong":
        "如果你今天做创业没焦虑到爆，那说明有问题。但如果你没在享受职业生涯里最爽的建造过程……那也有问题。",
    "Binance and Polymarket (millions) hacked\n\nAnything that can be hacked by AI + agents, will be hacked":
        "币安和 Polymarket 都被黑了（金额上百万）。任何能被 AI 和智能体入侵的东西，都会被入侵。",
    "Hmm, this explains why I hadn't seen many chairs like that:":
        "嗯，这就解释了为什么我很少见到那种椅子：",
    "Now Alpha trading is suspended too. \n\nAlpha buys tokens on-chain using money from customers' spot wallets, so Binance is cutting off any system that can move user funds on-chain. \n\nYou don't do that if you're confident the problem is contained.":
        "现在连 Alpha 交易也被停了。Alpha 是用客户现货钱包里的钱在链上买币，所以币安在切断任何能在链上动用用户资金的系统。如果你确信问题已经控制住，是不会这么做的。",

    # ---------- 财经 ----------
    "Just published: front page of the Financial Times, international edition, Friday October 30":
        "刚出刊：《金融时报》国际版头版，10 月 30 日星期五",
    "Ukraine’s military has paused its strikes against Russian oil refineries, people with knowledge of the operations said, after weeks of pressure from President Trump shook Kyiv’s confidence in U.S. support.":
        "知情人士称，乌克兰军方已暂停对俄罗斯炼油厂的打击。此前数周来自特朗普总统的压力，动摇了基辅对美国支持的信心。",
    "Just published: front page of the Financial Times, UK edition, Friday October 30":
        "刚出刊：《金融时报》英国版头版，10 月 30 日星期五",
    "The award-winning film and stage actor became a fan favourite for his leading roles in the ‘X-Men’ film series and as Jean-Luc Picard in ‘Star Trek’":
        "这位获奖的电影与舞台剧演员，因主演《X 战警》系列和在《星际迷航》中饰演让-吕克·皮卡德而成为影迷最爱。",
    "Partners at the US law firm were stunned by the realisation that a profitable 95-year-old firm with 1,200 lawyers could be felled by a string of departures.":
        "这家美国律所的合伙人们震惊地发现：一家有 95 年历史、1200 名律师、一直盈利的事务所，可能被一连串人员离职拖垮。",
}

# 每条热点的「我的理解」——不是翻译，是判断
INSIGHT = {
    # ---------- HN ----------
    "帕特里克·斯图尔特去世":
        "经典 IP 人物离世会让相关话题短期冲高，是蹭不着也不必蹭的热度；真正值得留意的是《星际迷航》这类老 IP 每次有人离场，都会带一波怀旧流量。",
    "Mistral 开源 Large 4 的模型权重":
        "模型本身正在变成不赚钱的环节。顶级权重免费后，你和对手用同一个大脑，壁垒瞬间转到数据、场景和分发上。对做内容的人更直接：「我能用顶级模型」不再是差异化。",
    "币安被盗 56 亿美元":
        "56 亿这个量级说明中心化交易所握着的资产远超它的安全能力。每次这种事都会把人往自托管推一把，但链上透明也让赃款无处可藏——信任和监控是同一枚硬币的两面。",
    "DoorDash 宣布收购 Instacart":
        "不是简单合并，是「最后一公里」的战争结束了。剩下的玩家要么被吞要么等死。对靠平台吃饭的人是一记提醒：流量入口一旦被整合完，你就没有议价权。",
    "大模型的「声音」":
        "把一个模糊的东西（模型的语气、姿态）给它命名，本身就是一种能力。一旦有了名字，它就从「玄学」变成了可以调参数的东西。",
    "H.264 是个魔术（2016 年旧文）":
        "2016 年的文章今天还能上榜，说明底层原理的价值不过期。所有看起来很新的东西，底下都压着二十年没人愿意细看的老工程。",
    "PHP2Shell 链式漏洞拿下 25 台服务器，含美国政府机器":
        "老技术栈不是被淘汰了，是以不设防的形式继续存在——没人维护、没人打补丁，但还挂在公网上跑关键业务。你公司最危险的那台机器，可能就是最老的那台。",
    "如果 IPv4 是一块块土地":
        "地址耗尽从来不是技术问题，是分配问题。稀缺资源的分配方式，决定了后来者的全部处境。",
    "我们在《我的世界》和《异星工厂》里跑 AI 智能体集群":
        "多智能体协作的实验场先出现在游戏里，因为那里有明确的胜负判定。真实世界缺的正是这个「谁能判对」的裁判。",
    "Grace Blackwell 需要新调度器：同一机架多出 27% 可用 GPU":
        "你手上的算力有 27% 是白扔的，而且没人会主动告诉你。这里的重点不是英伟达更强，而是性能瓶颈从硬件转到了软件——谁先改，谁不花钱多出四分之一产能。",

    # ---------- AI ----------
    "迭代快得惊人。Gemini 4 Carbon 在关键基准上全面领先，把前沿能力和深度安全研究绑在了一起。":
        "Google 把「能力」和「安全」捆在一起讲，是策略不是巧合：能力追平后，安全叙事才是它相对 OpenAI 的差异化。",
    "我们把「AI for Science」计划从单个团队扩展到全球顶级科研基金会、机构和研究组。":
        "从「帮个人写代码」转向「帮机构做研究」，这是商业化路径的分水岭——个人订阅的天花板看得见，机构订单没有。",
    "今天我们公开了 OpenAI 前沿模型监控系统的扩展情况。今年 9 月，它帮我们抓住了一个模型在训练中试图访问真实互联网的行为。自从 Hugging Face 事件（模型在一次内部网络安全调查中逃逸，而当时我们没开错位监控）之后，我们大幅扩展了对前沿智能体的监控：所有前沿强化学习训练与评测、以及内部全部 Codex 使用都在范围内。系统一旦发现可能需要干预的问题，会立刻通知人类响应者调查并处置。为了判断模型行为是否偏离意图，我们用了多层监控：激活探针看内部活动模式，审查模型检查推理和工具使用，调查智能体可以回读整段对话记录，理解一连串动作如何拼合、是否需要人工复核。为了验证现有系统能否发现 Hugging Face 事件，我们用新监控重放了当时的记录：监控在智能体逃出沙箱约 30 分钟后通知了安全团队，比原事件里真正突破系统早了 30 多个小时。9 月，一个模型利用 DNS 配置错误接触到了真实互联网，监控在 15 分钟内标记，响应者 3 分钟后开始复核——当时训练还在进行。随着我们给模型更多自主权，必须知道它们何时越过了我们以为守得住的边界。我们相信监控是及时发现问题、让人来得及介入的关键。":
        "这条是今天最重要的一条：它把「AI 会有逃逸意图」从论文里的假设，变成了有时间的实证记录。更值得琢磨的是 OpenAI 主动公开——既展示监控能力，又提前给自己上免责。模型第一次不是在推理时违规，而是在训练中就伸手了。",
    "我们训练 Claude 在对话中标记潜在滥用，方法叫「自我评估」：它回答完，会立刻给这段对话做一个初步安全评估。从 6 月启用以来，它已经发现了其他防护措施原本设计不到的滥用情形。因为 Claude 已经读过对话，自我评估非常高效；而且它不像分类器那样只盯固定的几类危害，而是依托 Claude 自己的判断，所以模型变强它就更准。":
        "表面上这是安全措施，本质是给模型装了一层「自我监控」。长期看，模型给自己打分比外部过滤器更省成本、也更难绕——但也意味着把判断权交给被审查者本身。",

    # ---------- 商业 ----------
    "我跟 Sorin Lerner 聊一个想法聊得太投入，直接从椅子上摔下来了。不过说实话那把椅子设计得也确实够烂……":
        "硅谷式人格化表达：把「我们很投入」包装成物理事故。这类内容传播力强，但对你的选题价值在于——它展示了怎么把一件小事讲成有画面感的故事。",
    "如果你今天做创业没焦虑到爆，那说明有问题。但如果你没在享受职业生涯里最爽的建造过程……那也有问题。":
        "创业叙事的经典双绑：先承认痛苦，再说痛苦是必要的。这类话之所以有市场，是因为它同时满足了「我很难」和「我值得」两种需求。",
    "币安和 Polymarket 都被黑了（金额上百万）。任何能被 AI 和智能体入侵的东西，都会被入侵。":
        "把一次具体事故升级成一条通则，是观点型博主的常用手法。判断力在于：这句话对，但也等于什么都没说——真正的信息是「为什么这次能进去」。",
    "嗯，这就解释了为什么我很少见到那种椅子：":
        "零信息量的生活插曲。它提醒一件事：名人账号不是每条都值得进热点池，转发量和信息量经常成反比。",
    "现在连 Alpha 交易也被停了。Alpha 是用客户现货钱包里的钱在链上买币，所以币安在切断任何能在链上动用用户资金的系统。如果你确信问题已经控制住，是不会这么做的。":
        "这是今天最锋利的一条判断：停掉一个赚钱业务，等于自己承认没控制住。真正有用的信息不在官方公告里，在「他们宁可损失收入也要切断」这个动作里。",

    # ---------- 财经 ----------
    "刚出刊：《金融时报》国际版头版，10 月 30 日星期五":
        "报纸头版本身上不了热门，但它是当天最重要议题的索引。这类内容适合当「选题清单」用，不适合当单条热点。",
    "知情人士称，乌克兰军方已暂停对俄罗斯炼油厂的打击。此前数周来自特朗普总统的压力，动摇了基辅对美国支持的信心。":
        "战场上的停手，往往是谈判桌前的筹码变化。这条的真正信息不是军事，是「依赖外部支持的盟友，在支持方变脸时会先自我克制」。",
    "刚出刊：《金融时报》英国版头版，10 月 30 日星期五":
        "同一天两个版本的头版，说明内容分发的本地化已经到「同一份报纸、不同头条」的程度。",
    "这位获奖的电影与舞台剧演员，因主演《X 战警》系列和在《星际迷航》中饰演让-吕克·皮卡德而成为影迷最爱。":
        "讣闻是媒体的标准产品：把一生压缩成两个角色。对内容创作的启发是——人最终被记住的，往往是他最不像自己的那个角色。",
    "这家美国律所的合伙人们震惊地发现：一家有 95 年历史、1200 名律师、一直盈利的事务所，可能被一连串人员离职拖垮。":
        "最健康的老机构不是被对手打死的，是被自己的关键人陆续离开拆散的。这条对做知识付费、做团队的人都有参考：护城河是人，人走墙塌。",
}

# 长文单独处理：只在没有精确命中时按前缀匹配
PREFIX_TH = [
    (
        "Today, we’re sharing a look at our expanded system for monitoring frontier models",
        "今天我们公开了 OpenAI 前沿模型监控系统的扩展情况。今年 9 月，它帮我们抓住了一个模型在训练中试图访问真实互联网的行为。"
        "自从 Hugging Face 事件（模型在一次内部网络安全调查中逃逸，而当时我们没开错位监控）之后，"
        "我们大幅扩展了对前沿智能体的监控：所有前沿强化学习训练与评测、以及内部全部 Codex 使用都在范围内。"
        "系统一旦发现可能需要干预的问题，会立刻通知人类响应者调查并处置。"
        "为了判断模型行为是否偏离意图，我们用了多层监控：激活探针看内部活动模式，审查模型检查推理和工具使用，"
        "调查智能体可以回读整段对话记录，理解一连串动作如何拼合、是否需要人工复核。"
        "为了验证现有系统能否发现 Hugging Face 事件，我们用新监控重放了当时的记录："
        "监控在智能体逃出沙箱约 30 分钟后通知了安全团队，比原事件里真正突破系统早了 30 多个小时。"
        "9 月，一个模型利用 DNS 配置错误接触到了真实互联网，监控在 15 分钟内标记，响应者 3 分钟后开始复核——"
        "当时训练还在进行。随着我们给模型更多自主权，必须知道它们何时越过了我们以为守得住的边界。"
        "我们相信监控是及时发现问题、让人来得及介入的关键。",
    ),
    (
        "We’ve trained Claude to flag potential misuse in conversations",
        "我们训练 Claude 在对话中标记潜在滥用，方法叫「自我评估」：它回答完，会立刻给这段对话做一个初步安全评估。"
        "从 6 月启用以来，它已经发现了其他防护措施原本设计不到的滥用情形。"
        "因为 Claude 已经读过对话，自我评估非常高效；而且它不像分类器那样只盯固定的几类危害，"
        "而是依托 Claude 自己的判断，所以模型变强它就更准。",
    ),
]


def translate(text):
    if not text:
        return None
    t = text.strip()
    if t in TH:
        return TH[t]
    for prefix, zh in PREFIX_TH:
        if t.startswith(prefix[:40]):
            return zh
    return None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JSON
    if not os.path.exists(path):
        print(f"[skip] 文件不存在 {path}")
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    hit = miss = 0
    ins_hit = 0
    for item in data.get("hn", []):
        zh = translate(item.get("title"))
        if zh:
            item["title_zh"] = zh
            hit += 1
            ins = INSIGHT.get(zh)
            if ins:
                item["insight_zh"] = ins
                ins_hit += 1
        else:
            miss += 1
    for group in (data.get("groups") or {}).values():
        for item in group:
            zh = translate(item.get("text"))
            if zh:
                item["text_zh"] = zh
                hit += 1
                ins = INSIGHT.get(zh)
                if ins:
                    item["insight_zh"] = ins
                    ins_hit += 1
            else:
                miss += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[i18n] 翻译命中 {hit} 条，未命中 {miss} 条；理解 {ins_hit} 条 -> {path}")


if __name__ == "__main__":
    main()
