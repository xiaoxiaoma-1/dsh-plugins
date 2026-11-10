import json, re, sys, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8")

TARGETS = [
    ("The Diary Of A CEO", "us"),
    ("Huberman Lab", "us"),
    ("On Purpose with Jay Shetty", "us"),
    ("Jack Neel", "us"),
    ("Cleo Abram", "us"),
    ("毕英杰", "cn"),
    ("WhynotTV", "cn"),
    ("钦文和他的朋友们", "cn"),
]

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search(term, country):
    u = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": term, "entity": "podcast", "limit": 3, "country": country})
    try:
        d = json.loads(get(u, 20))
    except Exception as e:
        print("  搜索失败:", str(e)[:80])
        return []
    return d.get("results", [])


def dur_seconds(s):
    if not s:
        return 0
    s = s.strip()
    if ":" in s:
        p = [int(float(x)) for x in s.split(":")]
        if len(p) == 3:
            return p[0] * 3600 + p[1] * 60 + p[2]
        if len(p) == 2:
            return p[0] * 60 + p[1]
    try:
        return int(float(s))
    except Exception:
        return 0


def feed_stats(feed, n=10):
    try:
        xml = get(feed, 30).decode("utf-8", "ignore")
    except Exception as e:
        return None, str(e)[:80]
    items = re.findall(r"<item>([\s\S]*?)</item>", xml)
    durs = []
    mp3 = 0
    for it in items[:n]:
        d = re.search(r"<itunes:duration>([\s\S]*?)</itunes:duration>", it)
        if d:
            durs.append(dur_seconds(d.group(1)))
        if re.search(r'<enclosure[^>]*url="[^"]+\.(mp3|m4a)', it, re.I):
            mp3 += 1
    avg = sum(durs) / len(durs) / 60 if durs else 0
    return {"total": len(items), "avg_min": round(avg, 1), "mp3": mp3, "sample": min(n, len(items))}, None


for name, cc in TARGETS:
    print("\n===", name)
    res = search(name, cc)
    if not res:
        print("  没找到播客条目")
        continue
    for it in res[:2]:
        title = it.get("collectionName") or ""
        feed = it.get("feedUrl") or ""
        cnt = it.get("trackCount")
        print(f"  · {title[:50]} | 期数 {cnt} | {feed[:70]}")
        if feed:
            st, err = feed_stats(feed)
            if st:
                print(f"    近{st['sample']}期平均 {st['avg_min']} 分钟 | 有音频直链 {st['mp3']}/{st['sample']} | RSS 里共 {st['total']} 期")
            else:
                print("    RSS 抓取失败:", err)
