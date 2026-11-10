# -*- coding: utf-8 -*-
"""找 Derek Sivers 的 Anything You Want。"""
import io
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


def get(u, t=50):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "ignore")


ids = []
for q in ("Anything You Want Sivers", "Derek Sivers", "Anything You Want 40 lessons"):
    try:
        h = get("https://libgen.li/index.php?req=" + urllib.parse.quote(q) + "&res=50", 50)
    except Exception as e:
        print("搜「%s」失败 %s" % (q, str(e)[:40]))
        continue
    n0 = len(ids)
    for m in re.finditer(r'md5=([a-f0-9]{32})', h):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    print("搜「%s」→ 新增 %d（累计 %d）" % (q, len(ids) - n0, len(ids)))

print("\n共 %d 候选，查详情…\n" % len(ids))

picked = []
for md5 in ids:
    try:
        h = get("https://libgen.li/ads.php?md5=" + md5, 40)
    except Exception:
        continue
    t = re.sub(r'(?is)<script.*?</script>', ' ', h)
    t = re.sub(r'(?is)<style.*?</style>', ' ', t)
    t = re.sub(r'<[^>]+>', '\n', t)
    lines = [re.sub(r'\s+', ' ', x).strip() for x in t.split("\n") if x.strip()]
    title, author, year = "", "", ""
    for x in lines:
        if x.startswith("Title:") and not title:
            title = x[6:].strip()[:150]
        elif x.startswith("Author(s):") and not author:
            author = x[10:].strip()[:80]
        elif x.startswith("Year:") and not year:
            year = x[5:].strip()[:6]
    if not title:
        continue
    tl = title.lower()
    if "anything you want" not in tl and "sivers" not in (author or "").lower():
        continue
    m = re.search(r'get\.php\?md5=' + md5 + r'&key=([A-Z0-9]+)', h)
    if not m:
        continue
    ext = "pdf"
    for e in ("epub", "pdf", "mobi", "azw3"):
        if re.search(r'\.' + e + r'\b', h, re.I):
            ext = e
            break
    picked.append({"md5": md5, "title": title, "author": author, "year": year, "ext": ext,
                   "dl": "https://libgen.li/get.php?md5=%s&key=%s" % (md5, m.group(1))})
    print("  ✓ [%s] %s | %s | %s | %s" % (md5[:8], title[:56], author[:24], year, ext))
    time.sleep(0.3)

print("\n命中 %d 条\n" % len(picked))

ok = 0
for it in picked[:4]:
    fn = os.path.join(OUT, "anything_you_want_%s.%s" % (it["year"] or it["md5"][:6], it["ext"]))
    try:
        with urllib.request.urlopen(urllib.request.Request(it["dl"], headers=UA), timeout=300) as r:
            data = r.read()
    except Exception as e:
        print("  下载失败 %s" % str(e)[:50])
        continue
    if not (data.startswith(b"%PDF") or data.startswith(b"PK")):
        print("  无效（%d 字节）" % len(data))
        continue
    open(fn, "wb").write(data)
    print("  ✓ %s  %.2f MB" % (os.path.basename(fn), len(data) / 1024 / 1024))
    ok += 1
    if ok >= 1:
        break

print("\n下了 %d 个" % ok)
