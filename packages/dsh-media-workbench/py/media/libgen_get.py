# -*- coding: utf-8 -*-
"""libgen.li 下载器：按 md5 拿文件，落盘到指定目录"""
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
      "Referer": "https://libgen.li/"}


def search_full(kw, limit=30):
    """返回带完整 md5 的搜索结果"""
    url = "https://libgen.li/index.php?req=" + urllib.parse.quote(kw)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        html = r.read().decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', html, re.S):
        t = m.group(1)
        md5 = re.search(r"md5=([0-9a-f]{32})", t)
        if not md5:
            continue
        tt = re.search(r'edition\.php\?id=\d+">(.*?)</a>', t, re.S)
        ext = re.findall(r"\b(pdf|epub|mobi|azw3|djvu|txt)\b", t, re.I)
        size = re.search(r"(\d+(?:\.\d+)?\s?(?:MB|KB|GB))", t, re.I)
        out.append({"title": re.sub(r"<[^>]+>", "", tt.group(1)).strip()[:100] if tt else "",
                    "md5": md5.group(1), "ext": ext[0].lower() if ext else "",
                    "size": size.group(1) if size else ""})
    seen, res = set(), []
    for x in out:
        if x["md5"] in seen:
            continue
        seen.add(x["md5"])
        res.append(x)
    return res[:limit]


def download(md5, ext, outdir, name=None):
    os.makedirs(outdir, exist_ok=True)
    # libgen.li 的真实下载路径在 ads.php 或直接 get.php
    for path in ["/get.php?md5=%s", "/ads.php?md5=%s"]:
        url = "https://libgen.li" + (path % md5)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                ctype = r.headers.get("Content-Type", "")
                data = r.read()
            if "html" in ctype.lower() and len(data) < 200000:
                # 是中间页，找下载链接
                html = data.decode("utf-8", "ignore")
                cand = re.findall(r'(?:href|location)\s*=\s*["\']([^"\']*(?:get\.php|\.(?:pdf|epub|mobi|azw3))[^"\']*)', html, re.I)
                for cu in cand[:3]:
                    full = cu if cu.startswith("http") else "https://libgen.li/" + cu.lstrip("/")
                    try:
                        with urllib.request.urlopen(urllib.request.Request(full, headers=UA), timeout=120) as r2:
                            d2 = r2.read()
                        if len(d2) > 50000:
                            fn = os.path.join(outdir, name or (md5 + "." + (ext or "bin")))
                            open(fn, "wb").write(d2)
                            return fn, len(d2)
                    except Exception:
                        continue
                continue
            if len(data) > 20000:
                fn = os.path.join(outdir, name or (md5 + "." + (ext or "bin")))
                open(fn, "wb").write(data)
                return fn, len(data)
        except Exception as e:
            last = str(e)[:60]
    return None, 0


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "毛泽东选集"
    hits = search_full(kw)
    print("搜到 %d 条：" % len(hits))
    for h in hits[:8]:
        print("  [%s %s] %s | %s" % (h["ext"] or "?", h["size"], h["title"][:60], h["md5"]))
    # 试下第一个 epub/mobi/azw3/pdf
    for h in hits:
        if h["ext"] in ("epub", "mobi", "azw3", "pdf"):
            fn, n = download(h["md5"], h["ext"], r"E:\wengao_新书")
            print("\n下载尝试：%s -> %s (%d 字节)" % (h["title"][:50], fn, n))
            break
