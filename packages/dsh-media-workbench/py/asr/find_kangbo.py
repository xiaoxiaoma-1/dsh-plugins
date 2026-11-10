# -*- coding: utf-8 -*-
"""在 libgen 上找《人生财富靠康波》/《涛动周期论》（周金涛）。"""
import io
import re
import sys
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
      "Referer": "https://libgen.li/"}


def get(u, t=45):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "ignore")


def search(q):
    try:
        h = get("https://libgen.li/index.php?req=" + urllib.parse.quote(q) + "&res=50")
    except Exception:
        return []
    out = []
    for m in re.finditer(r'md5=([a-f0-9]{32})', h):
        if m.group(1) not in out:
            out.append(m.group(1))
    return out


def detail(md5):
    try:
        h = get("https://libgen.li/ads.php?md5=" + md5, 40)
    except Exception:
        return None
    t = re.sub(r'(?is)<script.*?</script>', ' ', h)
    t = re.sub(r'(?is)<style.*?</style>', ' ', t)
    t = re.sub(r'<[^>]+>', '\n', t)
    lines = [re.sub(r'\s+', ' ', x).strip() for x in t.split("\n") if x.strip()]
    info = {"md5": md5, "title": "", "author": "", "year": "", "pages": "", "dl": ""}
    for x in lines:
        if x.startswith("Title:") and not info["title"]:
            info["title"] = x[6:].strip()[:170]
        elif x.startswith("Author(s):") and not info["author"]:
            info["author"] = x[10:].strip()[:80]
        elif x.startswith("Year:") and not info["year"]:
            info["year"] = x[5:].strip()[:6]
    m = re.search(r'get\.php\?md5=' + md5 + r'&key=([A-Z0-9]+)', h)
    if m:
        info["dl"] = "https://libgen.li/get.php?md5=%s&key=%s" % (md5, m.group(1))
    return info if info["title"] else None


QUERIES = [
    "人生财富靠康波", "涛动周期论", "周金涛",
    "Zhou Jintao", "Tao Dong Zhou Qi Lun", "ren sheng cai fu kao kang bo",
    "康德拉季耶夫周期", "周期天王",
]

seen = set()
found = []
for q in QUERIES:
    ids = search(q)
    if not ids:
        print("「%s」→ 0 个候选" % q)
        continue
    print("「%s」→ %d 个候选" % (q, len(ids)))
    for md5 in ids[:8]:
        if md5 in seen:
            continue
        seen.add(md5)
        d = detail(md5)
        if not d:
            continue
        tl = d["title"]
        # 只要中文书名或含这些关键词的
        if re.search(r'[\u4e00-\u9fa5]', tl) or "kangbo" in tl.lower() or "zhou" in (d["author"] or "").lower():
            print("   ★ [%s] %s | %s | %s" % (md5[:8], tl[:56], d["author"][:22], d["year"]))
            found.append(d)

print("\n总计命中中文/相关: %d 条" % len(found))
