# -*- coding: utf-8 -*-
"""下载周金涛的书：涛动周期论 + 理论大集。"""
import io
import os
import re
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
      "Referer": "https://libgen.li/"}
OUT = r"E:\tools\asr\downloads"
os.makedirs(OUT, exist_ok=True)

CAND = [
    ("65bc1e92", "涛动周期论_周金涛_2017"),
    ("3f078dd6", "周金涛理论大集_2019"),
    ("9cb3277c", "周金涛理论大集_2019_b"),
    ("f4c1a744", "涛动周期论_2017_b"),
    ("d13c56aa", "涛动周期论_2017_c"),
]


def get(u, t=45):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "ignore")


def full_md5(prefix):
    """用前缀去搜，拿到完整 md5"""
    for q in ("涛动周期论", "周期天王"):
        try:
            h = get("https://libgen.li/index.php?req=" + urllib.parse.quote(q) + "&res=50", 50)
        except Exception:
            continue
        for m in re.finditer(r'md5=([a-f0-9]{32})', h):
            if m.group(1).startswith(prefix):
                return m.group(1)
    return None


import urllib.parse

ok = 0
for prefix, hint in CAND:
    md5 = full_md5(prefix)
    if not md5:
        print("  %s → 找不到完整 md5" % prefix)
        continue
    try:
        h = get("https://libgen.li/ads.php?md5=" + md5, 45)
    except Exception as e:
        print("  %s 详情失败 %s" % (prefix, str(e)[:40]))
        continue
    m = re.search(r'get\.php\?md5=' + md5 + r'&key=([A-Z0-9]+)', h)
    if not m:
        print("  %s → 没有下载链接" % prefix)
        continue
    dl = "https://libgen.li/get.php?md5=%s&key=%s" % (md5, m.group(1))
    # 判断扩展名
    ext = "pdf"
    for e in ("epub", "pdf", "mobi", "azw3", "djvu"):
        if re.search(r'\.' + e + r'\b', h, re.I):
            ext = e
            break
    fn = os.path.join(OUT, hint + "." + ext)
    try:
        with urllib.request.urlopen(urllib.request.Request(dl, headers=UA), timeout=400) as r:
            data = r.read()
    except Exception as e:
        print("  %s 下载失败 %s" % (prefix, str(e)[:50]))
        continue
    if not (data.startswith(b"%PDF") or data.startswith(b"PK")):
        print("  %s → 不是有效文件（%d 字节）" % (prefix, len(data)))
        continue
    open(fn, "wb").write(data)
    print("  ✓ %s  %.1f MB  (%s)" % (os.path.basename(fn), len(data) / 1024 / 1024, md5[:10]))
    ok += 1
    if ok >= 2:
        break
    time.sleep(1)

print("\n下到 %d 个" % ok)
