# -*- coding: utf-8 -*-
"""下载 14 本可替代的抽坏书，优先 epub/mobi/azw3 文字版（PDF 是扫描件，优先级最低）"""
import json, os, re, sys, time, zipfile
sys.path.insert(0, r"E:\desktop\media")
from libgen_get import search_full, download  # noqa

sys.stdout.reconfigure(encoding="utf-8")
OUT = r"E:\wengao_新书"

TARGETS = [
    ("走进我的交易室", "走进我的交易室"),
    ("游戏改变世界 ", "游戏改变世界"),
    ("盘口解析", "盘口解析"),
    ("万能测顶底宝典", "万能测顶底宝典"),
    ("实战操盘--从初级到大师", "实战操盘"),
    ("短线交易大师", "短线交易大师"),
    ("【高级波段交易】 约翰·凯恩", "高级波段交易"),
    ("异类：不一样的成功启示录 ", "异类：不一样的成功启示录"),
    ("穿布鞋的马云（高清完整版）", "穿布鞋的马云"),
    ("好男人病毒", "好男人病毒"),
    ("炒股的智慧", "炒股的智慧"),
    ("设计中的设计 原研哉 ", "设计中的设计"),
    ("数字化定量分析", "数字化定量分析"),
    ("《传统企业如何做电商及微电商》高清完整版 ", "传统企业如何做电商及微电商"),
]

PRI = {"epub": 0, "azw3": 1, "mobi": 2, "pdf": 3, "djvu": 9, "txt": 4}


def txt_of_file(path):
    """epub 直接读 zip；txt 直接读；其它返回 None"""
    low = path.lower()
    if low.endswith(".txt"):
        return open(path, encoding="utf-8", errors="ignore").read()
    if low.endswith(".epub"):
        try:
            parts = []
            with zipfile.ZipFile(path) as z:
                for n in sorted(z.namelist()):
                    if not n.lower().endswith((".xhtml", ".html", ".htm")):
                        continue
                    raw = z.read(n).decode("utf-8", "ignore")
                    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
                    raw = re.sub(r"<br\s*/?>|</p>|</div>|</h\d>", "\n", raw, flags=re.I)
                    raw = re.sub(r"<[^>]+>", "", raw)
                    raw = raw.replace("&nbsp;", " ")
                    parts.append(raw)
            return "\n".join(parts)
        except Exception:
            return None
    return None


log = []
for orig, kw in TARGETS:
    try:
        hits = search_full(kw, limit=20)
    except Exception as e:
        log.append({"书名": orig, "结果": "搜索失败 " + str(e)[:40]})
        continue
    core = re.sub(r"\s", "", kw)[:5]
    good = [h for h in hits if core in re.sub(r"\s", "", h["title"])]
    good.sort(key=lambda h: PRI.get(h["ext"], 8))
    done = False
    for h in good:
        if h["ext"] not in ("epub", "azw3", "mobi", "pdf", "txt"):
            continue
        fn, n = download(h["md5"], h["ext"], OUT, re.sub(r"[\\/:*?\"<>|]", "", kw)[:20] + "." + h["ext"])
        if fn:
            body = txt_of_file(fn)
            log.append({"书名": orig, "文件": os.path.basename(fn), "格式": h["ext"],
                        "字节": n, "可提取字数": len(body) if body else 0})
            print("✔ %s -> %s [%s] %d 字节，可提取 %s 字" % (orig[:24], os.path.basename(fn), h["ext"], n,
                                                        len(body) if body else 0), flush=True)
            done = True
            break
    if not done:
        log.append({"书名": orig, "结果": "下载失败"})
        print("✘ %s 下载失败" % orig[:30], flush=True)
    time.sleep(0.5)

json.dump(log, open(r"E:\desktop\media\_broken_downloaded.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
ok = [x for x in log if x.get("字节")]
print("\n成功 %d / %d" % (len(ok), len(TARGETS)))
