# -*- coding: utf-8 -*-
"""libgen.li 中文搜索：解析书名/格式/大小/下载链接"""
import re
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def search(q):
    url = "https://libgen.li/index.php?req=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "ignore")
    rows = []
    for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', html, re.S):
        t = m.group(1)
        if 'md5=' not in t and 'edition.php' not in t:
            continue
        title = re.search(r'<a href="[^"]*?/book/index\.php\?md5=[^"]*"[^>]*>(.*?)</a>', t, re.S)
        if not title:
            title = re.search(r'<td[^>]*>\s*<a[^>]*>(.*?)</a>', t, re.S)
        author = re.search(r'<td[^>]*>([^<]{2,60})</td>\s*<td[^>]*>\s*\d{4}', t, re.S)
        md5 = re.search(r'md5=([0-9a-f]{32})', t)
        ext = re.findall(r'\b(pdf|epub|mobi|azw3|djvu|txt)\b', t, re.I)
        size = re.search(r'(\d+(?:\.\d+)?\s?(?:MB|KB|GB))', t, re.I)
        lang = re.search(r'<td[^>]*>(\d+)\s*(MB|KB)?</td>', t)
        if title:
            clean = re.sub(r'<[^>]+>', '', title.group(1)).strip()
            if clean and len(clean) > 1:
                rows.append({
                    "title": clean[:110],
                    "md5": md5.group(1) if md5 else "",
                    "ext": (ext[0].lower() if ext else ""),
                    "size": size.group(1) if size else "",
                })
    # 去重
    seen, out = set(), []
    for r in rows:
        k = (r["title"], r["md5"])
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


if __name__ == "__main__":
    queries = sys.argv[1:] or ["知易行难王阳明", "王阳明全集", "王阳明心学", "传习录"]
    o = []
    for q in queries:
        o.append("=" * 50)
        o.append("搜索：%s" % q)
        try:
            rs = search(q)
        except Exception as e:
            o.append("  失败：" + str(e)[:100])
            continue
        o.append("  %d 条" % len(rs))
        for r in rs[:25]:
            o.append("  [%s %s] %s | md5=%s" % (r["ext"] or "?", r["size"] or "?", r["title"], r["md5"][:8]))
    open(r"E:\desktop\media\_libgen_out.txt", "w", encoding="utf-8").write("\n".join(o))
    print("done", sum(1 for x in o if x.startswith("  [")))
