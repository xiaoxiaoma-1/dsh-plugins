# -*- coding: utf-8 -*-
"""一次拿全量候选，再挑书下载（周金涛）。"""
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


# ① 一次搜完，收集所有 md5
ids = []
for q in ("涛动周期论", "周期天王", "周金涛"):
    try:
        h = get("https://libgen.li/index.php?req=" + urllib.parse.quote(q) + "&res=50", 50)
    except Exception as e:
        print("搜「%s」失败 %s" % (q, str(e)[:40]))
        continue
    n0 = len(ids)
    for m in re.finditer(r'md5=([a-f0-9]{32})', h):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    print("搜「%s」→ 新增 %d 个（累计 %d）" % (q, len(ids) - n0, len(ids)))

print("\n共 %d 个候选，逐个查详情…\n" % len(ids))

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
    title = ""
    for x in lines:
        if x.startswith("Title:"):
            title = x[6:].strip()[:170]
            break
    if not title:
        continue
    if "涛动周期论" not in title and "周金涛理论大集" not in title:
        continue
    m = re.search(r'get\.php\?md5=' + md5 + r'&key=([A-Z0-9]+)', h)
    if not m:
        continue
    ext = "pdf"
    for e in ("epub", "pdf", "mobi", "azw3"):
        if re.search(r'\.' + e + r'\b', h, re.I):
            ext = e
            break
    picked.append({"md5": md5, "title": title, "ext": ext,
                   "dl": "https://libgen.li/get.php?md5=%s&key=%s" % (md5, m.group(1))})
    print("  ✓ [%s] %s … %s" % (md5[:8], title[:56], ext))
    if len(picked) >= 8:
        break
    time.sleep(0.3)

print("\n可下的: %d 个\n" % len(picked))

# ② 下载：先下《理论大集》（最全），再下《涛动周期论》
done = 0
for want, hint in (("周金涛理论大集", "周金涛理论大集_2019"),
                   ("涛动周期论", "涛动周期论_周金涛")):
    for it in picked:
        if want not in it["title"]:
            continue
        fn = os.path.join(OUT, hint + "." + it["ext"])
        if os.path.exists(fn):
            print("  已有 %s，跳过" % os.path.basename(fn))
            done += 1
            break
        try:
            with urllib.request.urlopen(urllib.request.Request(it["dl"], headers=UA), timeout=600) as r:
                data = r.read()
        except Exception as e:
            print("  %s 下载失败 %s" % (hint, str(e)[:50]))
            continue
        if not (data.startswith(b"%PDF") or data.startswith(b"PK")):
            print("  %s → 无效（%d 字节）" % (hint, len(data)))
            continue
        open(fn, "wb").write(data)
        print("  ✓ %s  %.1f MB" % (os.path.basename(fn), len(data) / 1024 / 1024))
        done += 1
        break

print("\n完成，下了 %d 个" % done)
