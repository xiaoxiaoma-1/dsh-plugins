# -*- coding: utf-8 -*-
"""给每日灵感素材补「角度」与「问题」。

angle  ：今天这条能怎么变成内容（AI 写的判断，不是摘要）
question：拿这条能问出什么（一个能开场的问题）

以 atom id 为 key，幂等，可反复跑。
"""
import json
import os
import sys

PATH = r"E:\desktop\hot\idea-2026-10-30.json"

DATA = {
    # 深度不够就满足不了专家用户
    "2024Q4_": {
        "angle": "反向用：能被你服务的人，恰好是那些在这个问题上没你懂的人。所以别怕自己不够深——怕的是你连用户「浅在哪」都没摸清。",
        "question": "你上一次被用户问住，是什么问题？",
    },
}

# 按 knowledge 前缀做映射，比 id 稳
BY_TEXT = [
    (
        "第一个是自媒体流量的问题",
        "关键在「机制」层面——不是模仿他的风格，是他按了观众哪个按钮。一旦能说出按钮的名字，你就能在自己的选题里复制它，而不用抄他的样子。",
        "你最喜欢的那条视频，按的是你哪个按钮？",
    ),
    (
        "目前视频号和 b 站都推了一个功能",
        "流量和变现第一次在同一口井里。以前是「站内拿流量、站外做转化」，现在平台自己收钱——靠私域、社群做交付的人，护城河被削掉一层。",
        "如果平台自己就能收钱，你还需要那么多私域工具吗？",
    ),
    (
        "前段时间很焦虑，直到我找到了尬聊的正确使用方法",
        "焦虑的解药不是找更好的话题，是把手边的话题说透。「凡是能够说的事情，都能够说」——这句话本身就是选题方法论：选题不在远处，在你说得清的地方。",
        "你手里那个觉得「没什么可讲」的话题，能讲透几层？",
    ),
]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not os.path.exists(PATH):
        print(f"[skip] 不存在 {PATH}")
        return
    with open(PATH, "r", encoding="utf-8") as f:
        d = json.load(f)

    hit = 0
    for item in d.get("items", []):
        k = item.get("knowledge", "")
        for prefix, angle, q in BY_TEXT:
            if k.startswith(prefix):
                item["angle"] = angle
                item["question"] = q
                hit += 1
                break

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print(f"[idea] 补角度 {hit} 条 -> {PATH}")


if __name__ == "__main__":
    main()
