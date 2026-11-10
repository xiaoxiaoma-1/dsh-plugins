# -*- coding: utf-8 -*-
"""导出 51 本抽坏书清单 + 搜索 libgen 可替代版本"""
import json, re, sqlite3, sys, time, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"}
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()

rows = q("""select b.id, b.title, m.chars, m.pages, m.chunks, qq.tier
            from book_quality qq join books b on b.id=qq.book_id
            join book_metric m on m.book_id=qq.book_id
            where qq.intact=0 order by m.chars desc""")
print("抽坏 %d 本" % len(rows))
json.dump([{"id": r[0], "title": r[1], "chars": r[2], "pages": r[3], "chunks": r[4]} for r in rows],
          open(r"E:\desktop\media\_broken_list.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def clean_title(t):
    t = re.sub(r"(高清完整版|完整版|高清|扫描版|中英对照版|文字版|pdf|PDF|_|\[精品\])", "", t or "")
    t = re.sub(r"[\d]{3,}", "", t)
    t = re.sub(r"[《》\[\]【】()（）\-—]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def libgen_search(kw):
    url = "https://libgen.li/index.php?req=" + urllib.parse.quote(kw)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, str(e)[:40]
    hits = []
    for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', html, re.S):
        t = m.group(1)
        if "md5=" not in t:
            continue
        tt = re.search(r'edition\.php\?id=\d+">(.*?)</a>', t, re.S)
        md5 = re.search(r"md5=([0-9a-f]{32})", t)
        ext = re.findall(r"\b(pdf|epub|mobi|azw3|djvu|txt)\b", t, re.I)
        size = re.search(r"(\d+(?:\.\d+)?\s?(?:MB|KB|GB))", t, re.I)
        if tt:
            hits.append({"title": re.sub(r"<[^>]+>", "", tt.group(1)).strip()[:90],
                         "md5": md5.group(1) if md5 else "",
                         "ext": ext[0].lower() if ext else "",
                         "size": size.group(1) if size else ""})
    seen, out = set(), []
    for h in hits:
        if h["md5"] in seen:
            continue
        seen.add(h["md5"])
        out.append(h)
    return out, None


o = ["抽坏 51 本 + libgen 搜索结果", ""]
found = 0
for r in rows:
    kw = clean_title(r[1])[:40]
    hits, err = libgen_search(kw)
    o.append("【%s】%s字 %s页" % (r[1][:44], r[2], r[3]))
    if err:
        o.append("   搜索失败 %s" % err)
        continue
    # 只保留标题有交集的
    core = re.sub(r"\s", "", kw)[:6]
    good = [h for h in hits if core[:4] and core[:4] in re.sub(r"\s", "", h["title"])][:4]
    if good:
        found += 1
        for h in good:
            o.append("   ✔ [%s %s] %s | md5=%s" % (h["ext"] or "?", h["size"], h["title"][:60], h["md5"][:10]))
    else:
        o.append("   ✘ libgen 无匹配（%d 条无关结果）" % len(hits))
    time.sleep(0.4)
o.append("")
o.append("可找到替代版本：%d / %d 本" % (found, len(rows)))
open(r"E:\desktop\media\_broken_search.txt", "w", encoding="utf-8").write("\n".join(o))
print("可搜到 %d / %d" % (found, len(rows)))
