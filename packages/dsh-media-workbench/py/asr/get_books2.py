# -*- coding: utf-8 -*-
"""补下：熊彼特完整版 + Perez 技术革命与金融资本。"""
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


def get(u, t=45):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8", "ignore")


def candidates(q):
    out = []
    for qq in (q, q.replace(" ", "+")):
        try:
            h = get("https://libgen.li/index.php?req=" + urllib.parse.quote(qq) + "&res=50")
        except Exception:
            continue
        for m in re.finditer(r'md5=([a-f0-9]{32})', h):
            if m.group(1) not in out:
                out.append(m.group(1))
        if out:
            break
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
        elif x.startswith("Pages:") and not info["pages"]:
            info["pages"] = x[6:].strip()[:10]
    m = re.search(r'get\.php\?md5=' + md5 + r'&key=([A-Z0-9]+)', h)
    if m:
        info["dl"] = "https://libgen.li/get.php?md5=%s&key=%s" % (md5, m.group(1))
    return info if info["title"] else None


def dl_and_check(info, fn):
    if not info.get("dl"):
        return None
    try:
        with urllib.request.urlopen(urllib.request.Request(info["dl"], headers=UA), timeout=300) as r:
            data = r.read()
    except Exception as e:
        return ("err", str(e)[:50])
    if not data.startswith(b"%PDF"):
        return ("err", "不是 PDF（%d 字节）" % len(data))
    if len(data) < 500000:
        return ("err", "太小 %.1fMB" % (len(data) / 1024 / 1024))
    p = os.path.join(OUT, fn)
    open(p, "wb").write(data)
    return ("ok", "%.1fMB" % (len(data) / 1024 / 1024))


# ① 熊彼特：要完整书（页数 > 300）
print("=" * 60)
print("① 熊彼特《资本主义、社会主义与民主》完整版")
ids = candidates("Schumpeter Capitalism Socialism Democracy")
print("  候选:", len(ids))
for md5 in ids[:14]:
    d = detail(md5)
    if not d:
        continue
    tl = d["title"].lower()
    if "capitalism" not in tl or "socialism" not in tl:
        continue
    pg = d["pages"]
    print("  看: %s | %s页 | %s" % (d["title"][:52], pg or "?", d["author"][:20]))
    try:
        pn = int(re.sub(r"[^0-9]", "", pg) or 0)
    except Exception:
        pn = 0
    if pn and pn < 150:
        print("    页数太少，跳过")
        continue
    r = dl_and_check(d, "资本主义社会主义与民主_熊彼特_%s.pdf" % (d["year"] or "?"))
    print("    →", r)
    if r and r[0] == "ok":
        break
    time.sleep(0.6)

# ② Perez
print("=" * 60)
print("② Perez《技术革命与金融资本》")
for q in ("Technological Revolutions Financial Capital", "Carlota Perez", "Perez technological revolution"):
    ids = candidates(q)
    print("  查「%s」→ 候选 %d" % (q, len(ids)))
    if not ids:
        continue
    for md5 in ids[:12]:
        d = detail(md5)
        if not d:
            continue
        tl = d["title"].lower()
        if "technolog" not in tl and "perez" not in (d["author"] or "").lower():
            continue
        print("  看: %s | %s页 | %s" % (d["title"][:52], d["pages"] or "?", d["author"][:20]))
        r = dl_and_check(d, "技术革命与金融资本_Perez_%s.pdf" % (d["year"] or "?"))
        print("    →", r)
        if r and r[0] == "ok":
            break
        time.sleep(0.6)
    else:
        continue
    break
