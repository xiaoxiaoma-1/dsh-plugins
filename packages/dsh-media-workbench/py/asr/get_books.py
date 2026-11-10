# -*- coding: utf-8 -*-
"""从 libgen.li 按书名精确找书并下载。"""
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
      "Referer": "https://libgen.li/"}
OUT = r"E:\tools\asr\downloads"
os.makedirs(OUT, exist_ok=True)


def get(u, t=40):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "ignore")


def search_md5(q):
    try:
        h = get("https://libgen.li/index.php?req=" + urllib.parse.quote(q), 45)
    except Exception:
        return []
    out = []
    for m in re.finditer(r'md5=([a-f0-9]{32})', h):
        if m.group(1) not in out:
            out.append(m.group(1))
    return out


def detail(md5):
    """返回 {title, author, year, ext, dl} 或 None"""
    try:
        h = get("https://libgen.li/ads.php?md5=" + md5, 40)
    except Exception:
        return None
    t = re.sub(r'(?is)<script.*?</script>', ' ', h)
    t = re.sub(r'(?is)<style.*?</style>', ' ', t)
    t = re.sub(r'<[^>]+>', '\n', t)
    lines = [re.sub(r'\s+', ' ', x).strip() for x in t.split("\n")]
    lines = [x for x in lines if x]

    info = {"md5": md5, "title": "", "author": "", "year": "", "ext": "", "dl": ""}
    for x in lines:
        if x.startswith("Title:") and not info["title"]:
            info["title"] = x[6:].strip()[:160]
        elif x.startswith("Author(s):") and not info["author"]:
            info["author"] = x[10:].strip()[:80]
        elif x.startswith("Year:") and not info["year"]:
            info["year"] = x[5:].strip()[:6]
    m = re.search(r'get\.php\?md5=' + md5 + r'&key=([A-Z0-9]+)', h)
    if m:
        info["dl"] = "https://libgen.li/get.php?md5=%s&key=%s" % (md5, m.group(1))
    for e in ("pdf", "epub", "djvu", "mobi"):
        if re.search(r'\.' + e + r'\b', h, re.I):
            info["ext"] = e
            break
    return info if info["title"] else None


def download(info, name_hint):
    if not info.get("dl"):
        return None
    safe = re.sub(r'[\\/:*?"<>|]', "_", name_hint)[:80]
    fn = os.path.join(OUT, safe + "." + (info.get("ext") or "pdf"))
    try:
        with urllib.request.urlopen(urllib.request.Request(info["dl"], headers=UA), timeout=300) as r:
            data = r.read()
        if len(data) < 50000:
            return None
        open(fn, "wb").write(data)
        return (fn, len(data))
    except Exception as e:
        print("    下载失败:", str(e)[:60])
        return None


# 目标：英文关键词 → 认领条件（书名里必须含的词）
TARGETS = [
    ("Technological Revolutions and Financial Capital", ["technological", "revolution"], "技术革命与金融资本_Perez"),
    ("Capitalism Socialism and Democracy Schumpeter", ["capitalism", "socialism"], "资本主义社会主义与民主_熊彼特"),
    ("Kondratieff Waves", ["kondratieff"], "康波周期_Kondratieff"),
    ("Long Waves in Economic Life", ["long wave"], "长波_经济生活"),
]

for q, musts, hint in TARGETS:
    print("=" * 60)
    print("目标:", hint)
    ids = search_md5(q)
    print("  候选:", len(ids))
    found = 0
    for md5 in ids[:10]:
        d = detail(md5)
        if not d:
            continue
        tl = d["title"].lower()
        if not all(k in tl for k in musts):
            continue
        print("  ✓ %s | %s | %s | %s" % (d["title"][:60], d["author"][:24], d["year"], d["ext"]))
        got = download(d, hint + "_" + d["year"])
        if got:
            print("    已存 %s (%.1f MB)" % (os.path.basename(got[0]), got[1] / 1024 / 1024))
            found += 1
            break
        else:
            print("    下不动，试下一个")
        time.sleep(0.5)
    if not found:
        print("  没找到匹配的")
