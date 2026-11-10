# -*- coding: utf-8 -*-
"""下载《周金涛理论大集》套装（含涛动周期录上下册）。"""
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


# ① 收集候选
ids = []
for q in ("周期波动尽平生", "涛动周期录", "周金涛理论大集"):
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

print("\n共 %d 个候选，查详情找套装…\n" % len(ids))

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
            title = x[6:].strip()[:200]
            break
    if not title:
        continue
    # 只要套装/录（不要已入库的那本"论"）
    if not (("周期波动尽平生" in title) or ("涛动周期录" in title) or ("理论大集" in title)):
        continue
    if "涛动周期论" in title and "录" not in title and "大集" not in title:
        continue
    m = re.search(r'get\.php\?md5=' + md5 + r'&key=([A-Z0-9]+)', h)
    if not m:
        continue
    ext = "pdf"
    for e in ("epub", "pdf", "mobi", "azw3"):
        if re.search(r'\.' + e + r'\b', h, re.I):
            ext = e
            break
    size_hint = re.search(r'(\d+(?:\.\d+)?)\s*(MB|GB)', h, re.I)
    picked.append({"md5": md5, "title": title, "ext": ext,
                   "size": size_hint.group(0) if size_hint else "?",
                   "dl": "https://libgen.li/get.php?md5=%s&key=%s" % (md5, m.group(1))})
    print("  ✓ [%s] %s … %s %s" % (md5[:8], title[:64], ext, size_hint.group(0) if size_hint else ""))
    time.sleep(0.3)

print("\n套装候选: %d 个\n" % len(picked))

# ② 下载（按体积从大到小，大的通常是全套）
picked.sort(key=lambda x: -(float(re.sub(r'[^0-9.]', '', x["size"]) or 0) if "GB" not in x["size"] else 999))
ok = 0
for i, it in enumerate(picked[:4]):
    hint = "周金涛理论大集_%d" % (i + 1) if len(picked) > 1 else "周金涛理论大集"
    fn = os.path.join(OUT, hint + "." + it["ext"])
    if os.path.exists(fn) and os.path.getsize(fn) > 500000:
        print("  已有 %s" % os.path.basename(fn))
        ok += 1
        continue
    try:
        with urllib.request.urlopen(urllib.request.Request(it["dl"], headers=UA), timeout=900) as r:
            data = r.read()
    except Exception as e:
        print("  [%s] 下载失败 %s" % (it["md5"][:8], str(e)[:50]))
        continue
    if not (data.startswith(b"%PDF") or data.startswith(b"PK")):
        print("  [%s] 无效（%d 字节）" % (it["md5"][:8], len(data)))
        continue
    open(fn, "wb").write(data)
    print("  ✓ %s  %.1f MB" % (os.path.basename(fn), len(data) / 1024 / 1024))
    ok += 1
    if ok >= 3:
        break

print("\n下了 %d 个" % ok)
