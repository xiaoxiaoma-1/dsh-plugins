# -*- coding: utf-8 -*-
"""生成书库体检报告：系列结构 / 多格式重复 / 小说清单 / 建议。只读。"""
import csv
import os
import sys
from collections import defaultdict

ROOT = r"E:\wengao"
OUT = r"E:\desktop\书库盘点"
sys.path.insert(0, OUT)
from analyze import norm, classify  # 复用


def main():
    rows = []
    with open(os.path.join(OUT, "书目清单.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["size"] = float(r["大小MB"])
            r["path"] = os.path.join(ROOT, r["相对路径"])
            r["norm"] = norm(r["文件名"])
            r["ext"] = r["格式"].lower().lstrip(".")
            rows.append(r)

    L = []
    L.append("# 书库体检报告\n")
    L.append("根目录：`E:\\wengao`　书目文件：%d 个（%.1f GB）\n" % (
        len(rows), sum(r["size"] for r in rows) / 1024))

    # 1. 系列结构
    L.append("\n## 一、每个系列里装的是什么\n")
    by_top = defaultdict(list)
    for r in rows:
        by_top[r["顶层目录"]].append(r)
    for top, v in sorted(by_top.items(), key=lambda kv: -len(kv[1])):
        subs = defaultdict(int)
        for r in v:
            parts = r["相对路径"].split(os.sep)
            key = parts[1] if len(parts) > 2 else "（直接放文件）"
            subs[key] += 1
        L.append("### %s —— %d 个书文件 / %.0f MB" % (top, len(v), sum(x["size"] for x in v)))
        for k, n in sorted(subs.items(), key=lambda kv: -kv[1])[:8]:
            L.append("- %s（%d）" % (k[:46], n))
        L.append("")

    # 2. 多格式重复（同一本书存了 pdf/epub/mobi/docx）
    fmt_groups = defaultdict(list)
    for r in rows:
        fmt_groups[(r["顶层目录"].split(os.sep)[0], r["norm"])].append(r)
    multi = {k: v for k, v in fmt_groups.items() if len(set(x["ext"] for x in v)) > 1}
    waste = 0
    keep_suggest = {}
    for k, v in multi.items():
        # 优先保留 pdf（体积最大、最通用），其余视为重复
        v.sort(key=lambda x: -x["size"])
        keep = next((x for x in v if x["ext"] == "pdf"), v[0])
        keep_suggest[k] = keep
        waste += sum(x["size"] for x in v if x is not keep)
    L.append("\n## 二、同一本书存了多种格式（%d 组，可回收约 %.0f MB）\n" % (len(multi), waste))
    L.append("建议每组只留 PDF（体积最大、最通用），其余 epub/mobi/docx 删掉。若你手机用 epub 看，改成留 epub。\n")
    for k, v in list(multi.items())[:25]:
        names = " / ".join("%s(%.1fMB)" % (x["ext"], x["size"]) for x in sorted(v, key=lambda x: -x["size"]))
        L.append("- %s → %s" % (v[0]["文件名"][:44], names))

    # 3. 小说 / 文学
    novels = [r for r in rows if "文学·小说" in classify(r["文件名"])]
    L.append("\n## 三、文学/小说类（%d 个，%.0f MB）——要不要删你定\n" % (
        len(novels), sum(r["size"] for r in novels)))
    for r in sorted(novels, key=lambda x: -x["size"]):
        L.append("- %.1f MB　%s" % (r["size"], r["文件名"][:56]))

    # 4. 未分类最多的目录
    unc = [r for r in rows if classify(r["文件名"]) == ["未分类"]]
    L.append("\n## 四、未分类 %d 个（%.0f MB）——按目录分布\n" % (
        len(unc), sum(r["size"] for r in unc)))
    ud = defaultdict(int)
    for r in unc:
        ud[r["相对路径"].split(os.sep)[0]] += 1
    for k, n in sorted(ud.items(), key=lambda kv: -kv[1]):
        L.append("- %s：%d 个" % (k[:46], n))

    # 5. 体量提醒
    L.append("\n## 五、体量提醒\n")
    L.append("书只占 E:\\wengao 的 4%。同一个盘里还有约 **760 GB 的视频/音频课**（mp4 641GB、mp3 32GB、mkv 26GB、avi 13.6GB、flv 11.5GB、zip 45GB）。")
    L.append("这些不是书，是网课录屏和音频课。要不要一起处理，得你定——它们才是占空间的大头。\n")

    p = os.path.join(OUT, "体检报告.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print("OK 报告已写：", p)
    print("多格式重复组=%d 可回收=%.0f MB | 小说=%d 个 | 未分类=%d 个" % (
        len(multi), waste, len(novels), len(unc)))
    # 控制台只打小说和系列名
    print("\n小说清单：")
    for r in sorted(novels, key=lambda x: -x["size"]):
        print("  %.1f MB  %s" % (r["size"], r["文件名"][:56]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
