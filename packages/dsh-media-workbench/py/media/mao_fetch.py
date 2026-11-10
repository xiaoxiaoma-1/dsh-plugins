# -*- coding: utf-8 -*-
"""下载候选毛选版本 + epub 转文本 + 判断卷次与简繁"""
import os, re, sys, zipfile
sys.path.insert(0, r"E:\desktop\media")
from libgen_get import download  # noqa

sys.stdout.reconfigure(encoding="utf-8")
OUT = r"E:\wengao_新书"

cands = [
    ("5203620475c2fdf6efffb335183afe2b", "epub", "毛选_3MB"),
    ("3be2bdefe7d941102e4cf522e08a0287", "epub", "毛选_2MB"),
    ("54d0c77a2a193fcbfb37080a09b4b4e5", "epub", "毛选_第5卷"),
]


def epub_text(path):
    txt = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))]
        names.sort()
        for n in names:
            try:
                raw = z.read(n).decode("utf-8", "ignore")
            except Exception:
                continue
            raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
            raw = re.sub(r"<br\s*/?>|</p>|</div>|</h\d>", "\n", raw, flags=re.I)
            raw = re.sub(r"<[^>]+>", "", raw)
            raw = raw.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
            txt.append(raw)
    return "\n".join(txt)


for md5, ext, name in cands:
    fn, n = download(md5, ext, OUT, name + "." + ext)
    if not fn:
        print("%s 下载失败" % name)
        continue
    try:
        t = epub_text(fn)
    except Exception as e:
        print("%s 解压失败 %s" % (name, e))
        continue
    cn = sum(1 for ch in t[:100000] if "\u4e00" <= ch <= "\u9fff")
    trad = sum(t.count(x) for x in "書國學東發開關實現點農業產經濟運動戰線鋒銜")
    simp = sum(t.count(x) for x in "书国学东发开关实现点农业产经济运动战线锋衔")
    print("\n=== %s (%d 字节, 提取 %d 字) ===" % (name, n, len(t)))
    print("  前 200 字: %s" % t[:200].replace("\n", " "))
    print("  繁体字 %d / 简体字 %d → %s" % (trad, simp, "繁体" if trad > simp else "简体"))
    for kw in ["第一卷", "第二卷", "第三卷", "第四卷", "第五卷", "矛盾论", "实践论", "湖南农民运动"]:
        print("    含'%s': %d 次" % (kw, t.count(kw)))
    open(os.path.join(OUT, name + ".txt"), "w", encoding="utf-8").write(t)
