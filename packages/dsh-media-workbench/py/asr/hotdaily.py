# -*- coding: utf-8 -*-
"""每日热点聚合：Hacker News + X 固定账号原创，筛选后输出 Markdown。"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

OUT_DIR = r"E:\desktop\hot"
HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"
AGENT_REACH = os.path.expandvars(r"%USERPROFILE%\.local\bin\agent-reach.exe")

ACCOUNTS = {
    "AI": ["sama", "karpathy", "ylecun", "demishassabis", "OpenAI", "AnthropicAI"],
    "商业": ["paulg", "naval", "jasonlk", "danielgross"],
    "财经": ["business", "WSJ", "FT"],
}

BAD_PATTERN = ["fashion show", "good morning", "lol", "😂😂", "彩票", "约炮"]

PROXY = "http://127.0.0.1:7897"


def get_json(url, timeout=20, use_proxy=True):
    headers = {"User-Agent": "Mozilla/5.0"}
    if use_proxy and PROXY:
        # HN 在国内直连不稳定，走代理更可靠
        op = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
        )
        req = urllib.request.Request(url, headers=headers)
        with op.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_hn(max_items=25):
    out = []
    try:
        ids = get_json(HN_TOP)
    except Exception as e:
        print(f"HN_FAIL {e}", file=sys.stderr)
        return out
    for i in ids[:max_items]:
        try:
            it = get_json(HN_ITEM.format(i), timeout=10)
        except Exception:
            continue
        if not it or not it.get("title"):
            continue
        ts = datetime.fromtimestamp(it.get("time", 0), tz=timezone.utc)
        age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        out.append({
            "score": int(it.get("score", 0)),
            "title": it.get("title", ""),
            "url": it.get("url") or f"https://news.ycombinator.com/item?id={i}",
            "time": ts.astimezone().strftime("%m-%d %H:%M"),
            "age_h": round(age_h, 1),
        })
    return out


def run_reach(args):
    env = dict(os.environ)
    env["HTTP_PROXY"] = PROXY
    env["HTTPS_PROXY"] = PROXY
    env["ALL_PROXY"] = PROXY
    # Windows 下完全不创建控制台窗口，避免抓取时闪黑框
    flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
    try:
        p = subprocess.run(
            [AGENT_REACH] + args,
            capture_output=True, timeout=120, env=env,
            creationflags=flags,
        )
        return p.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"REACH_FAIL {args} {e}", file=sys.stderr)
        return ""


def fetch_x():
    out = []
    for group, handles in ACCOUNTS.items():
        for h in handles:
            raw = run_reach(["twitter", "tweets", h, "--limit", "6"])
            try:
                o = json.loads(raw)
            except Exception:
                continue
            if not o.get("ok"):
                continue
            for item in o.get("items", []):
                r = item.get("raw") or {}
                if r.get("is_retweet"):
                    continue
                import re
                txt = re.sub(r"https?://\S+", "", r.get("text", "")).strip()
                if len(txt) < 40:
                    continue
                try:
                    dt = datetime.strptime(r["created_at"], "%a %b %d %H:%M:%S %z %Y")
                except Exception:
                    continue
                ago_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                views = re.sub(r"[^0-9]", "", str(r.get("views", "0"))) or "0"
                out.append({
                    "group": group,
                    "author": r.get("author", h),
                    "likes": int(r.get("likes", 0) or 0),
                    "views": int(views),
                    "text": txt,
                    "time": dt.astimezone().strftime("%m-%d %H:%M"),
                    "ago_h": round(ago_h, 1),
                    "url": r.get("url", ""),
                })
    return out


def kill_browser_watcher():
    """收尾：关掉 Agent Reach 的 browser_watcher 及其 Windows Terminal 窗口。

    Agent Reach 会常驻一个 browser_watcher 用于复用浏览器会话，
    它在 Windows 上会留下一个可见的终端窗口，用户不希望桌面上出现。
    """
    if os.name != "nt":
        return
    flags = 0x08000000
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -match 'browser_watcher' } | "
        "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }; "
        "Get-Process WindowsTerminal -ErrorAction SilentlyContinue | "
        "Where-Object { $_.MainWindowTitle -match 'cloakbrowser|agent-reach' } | "
        "ForEach-Object { try { Stop-Process -Id $_.Id -Force -ErrorAction Stop } catch {} }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            capture_output=True, timeout=30, creationflags=flags,
        )
    except Exception:
        pass


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")

    hn = fetch_hn()
    tw = fetch_x()

    hn_top = sorted([x for x in hn if x["age_h"] <= 36], key=lambda x: -x["score"])[:10]
    tw_pool = [x for x in tw if x["ago_h"] <= 48 and not any(b in x["text"].lower() for b in BAD_PATTERN)]

    L = []
    L.append(f"# 今日热点 {stamp}")
    L.append("")
    L.append("## 一、全球科技前沿（Hacker News · 36 小时内）")
    L.append("")
    if not hn_top:
        L.append("（无）")
    for x in hn_top:
        L.append(f"- **[{x['score']} 分]** {x['title']}")
        L.append(f"  {x['url']} · {x['time']}")
    L.append("")

    # X 按分组输出
    group_titles = {"AI": "二、AI 圈在聊什么", "商业": "三、商业与创业", "财经": "四、财经与宏观"}
    idx = 0
    for group in ACCOUNTS.keys():
        idx += 1
        g = sorted([x for x in tw_pool if x["group"] == group], key=lambda x: -x["likes"])[:5]
        title = group_titles.get(group, f"第{idx}组 {group}")
        L.append(f"## {title}（X 原创 · 48 小时内）")
        L.append("")
        if not g:
            L.append("（无）")
        for x in g:
            t = x["text"] if len(x["text"]) <= 220 else x["text"][:220] + "…"
            L.append(f"- **@{x['author']}** · {x['likes']} 赞 · {x['views']} 浏览 · {x['time']}")
            L.append(f"  {t}")
            L.append(f"  {x['url']}")
        L.append("")

    L.append("---")
    L.append(f"抓取：HN {len(hn)} 条 / X {len(tw)} 条 → 筛选后 {len(hn_top)} + {len(tw_pool)} 条")

    md = "\n".join(L)
    path = os.path.join(OUT_DIR, f"hot-{stamp}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)

    # 结构化数据，供工作台界面读取
    groups_out = {}
    for group in ACCOUNTS.keys():
        g = sorted([x for x in tw_pool if x["group"] == group], key=lambda x: -x["likes"])[:5]
        groups_out[group] = [
            {"author": x["author"], "likes": x["likes"], "views": x["views"],
             "text": x["text"], "time": x["time"], "url": x["url"]}
            for x in g
        ]
    payload = {
        "date": stamp,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "hn": [{"score": x["score"], "title": x["title"], "url": x["url"], "time": x["time"]} for x in hn_top],
        "groups": groups_out,
        "counts": {"hn_raw": len(hn), "x_raw": len(tw), "hn_kept": len(hn_top),
                   "x_kept": sum(len(v) for v in groups_out.values())},
    }
    jpath = os.path.join(OUT_DIR, f"hot-{stamp}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(md)
    print(f"\n[saved] {path}")
    print(f"[saved] {jpath}")

    # 收尾：清掉 Agent Reach 留下的终端窗口
    kill_browser_watcher()


if __name__ == "__main__":
    main()
