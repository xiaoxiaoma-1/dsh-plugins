# -*- coding: utf-8 -*-
"""E:\\wengao 盘点：按顶层文件夹统计 + 导出书目清单。只读，不动文件。"""
import csv
import os
import sys

ROOT = r"E:\wengao"
OUT = r"E:\desktop\书库盘点"
GROUPS = {
    "book": {".pdf", ".epub", ".mobi", ".ebk3", ".azw3", ".djvu", ".chm", ".txt", ".doc", ".docx", ".mht", ".mhtml"},
    "video": {".mp4", ".flv", ".avi", ".mkv", ".rm", ".rmvb", ".wmv", ".m4v", ".mov"},
    "audio": {".mp3", ".m4a", ".aac", ".wav", ".flac"},
    "image": {".jpg", ".png", ".gif", ".bmp", ".webp"},
    "archive": {".zip", ".rar", ".7z", ".gz", ".tar"},
}


def group_of(ext):
    e = ext.lower()
    for k, s in GROUPS.items():
        if e in s:
            return k
    return "other"


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            rel = os.path.relpath(p, ROOT)
            top = rel.split(os.sep)[0] if os.sep in rel else "（根目录）"
            ext = os.path.splitext(fn)[1].lower()
            rows.append({
                "top": top, "rel": rel, "name": fn, "ext": ext,
                "group": group_of(ext), "size": st.st_size,
                "mtime": int(st.st_mtime),
            })

    # 汇总
    from collections import defaultdict
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        a = agg[r["top"]]
        a[r["group"]][0] += 1
        a[r["group"]][1] += r["size"]

    print("== 按顶层文件夹（书/视频/音频/图/压缩/其他, 大小GB）==")
    tops = sorted(agg.items(), key=lambda kv: -sum(v[1] for v in kv[1].values()))
    for top, g in tops:
        total = sum(v[1] for v in g.values()) / 1024 ** 3
        parts = " ".join("%s=%d" % (k, g[k][0]) for k in ("book", "video", "audio", "image", "archive", "other") if g.get(k))
        print("%7.1f GB | %-36s | %s" % (total, top[:36], parts))

    # 书目清单
    books = [r for r in rows if r["group"] == "book"]
    books.sort(key=lambda r: r["rel"])
    p1 = os.path.join(OUT, "书目清单.csv")
    with open(p1, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["相对路径", "文件名", "格式", "大小MB", "顶层目录"])
        for r in books:
            w.writerow([r["rel"], r["name"], r["ext"], round(r["size"] / 1024 ** 2, 2), r["top"]])

    # 全量清单
    p2 = os.path.join(OUT, "全量清单.csv")
    with open(p2, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["相对路径", "类型", "格式", "大小MB", "顶层目录"])
        for r in sorted(rows, key=lambda r: r["rel"]):
            w.writerow([r["rel"], r["group"], r["ext"], round(r["size"] / 1024 ** 2, 2), r["top"]])

    print("\n== 合计 ==")
    print("文件 %d 个，%.1f GB；其中书 %d 个（%.1f GB）" % (
        len(rows), sum(r["size"] for r in rows) / 1024 ** 3,
        len(books), sum(r["size"] for r in books) / 1024 ** 3))
    print("已写：", p1)
    print("已写：", p2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
