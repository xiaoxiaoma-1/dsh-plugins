# -*- coding: utf-8 -*-
"""同名不同版本查重：同名的书按页数比，保留页数最多的，其余列为待删。

默认 dry-run。
归一化会保留「第X版 / 修订 / 增补 / 全译本 / 上下册」这些区分词，只去掉下载噪声。
"""
import os
import re
import sys

import fitz

ROOT = r"E:\wengao"
NOISE = re.compile(r"[（(](无水印|防封版|不防封版|防和谐|完整版|高清版|扫描版|文字版|电子版|\d{1,2})[）)]|副本|-\s*副本") 
KEEP_WORDS = re.compile(r"(第[一二三四五六七八九十\d]+版|修订|增补|全译本|上册|下册|上卷|下卷|第[一二三四五六七八九十]+[册卷部篇])")


def norm(name):
    s = os.path.splitext(name)[0].lower()
    s = NOISE.sub("", s)
    s = re.sub(r"[\s\.\-_·,，、:：;；'\"“”‘’]+", "", s)
    return s


def pages_of(p):
    try:
        d = fitz.open(p)
        n = d.page_count
        d.close()
        return n
    except Exception:
        return -1


def main():
    apply = "--apply" in sys.argv
    files = []
    for dp, _, fs in os.walk(ROOT):
        if "_原格式" in dp or "_已解压" in dp:
            continue
        for f in fs:
            if f.lower().endswith(".pdf"):
                files.append(os.path.join(dp, f))

    groups = {}
    for p in files:
        groups.setdefault(norm(os.path.basename(p)), []).append(p)

    dup = {k: v for k, v in groups.items() if len(v) > 1}
    # 纯数字文件名（如毛泽东全集 11.pdf）不是同名重复，是不同卷，跳过
    dup = {k: v for k, v in dup.items() if not re.fullmatch(r"\d{1,3}", k)}
    print("PDF %d 本，同名分组 %d 组（已剔除纯数字名）" % (len(files), len(dup)))

    plan = []
    for k, v in dup.items():
        info = [(pages_of(p), os.path.getsize(p), p) for p in v]
        info.sort(key=lambda x: (-x[0], -x[1]))
        keep = info[0]
        for n, sz, p in info[1:]:
            plan.append((k, keep, (n, sz, p)))

    total = sum(x[2][1] for x in plan) / 1024 ** 2
    print("待删 %d 个，可回收 %.1f MB\n" % (len(plan), total))
    for k, keep, (n, sz, p) in plan[:30]:
        print("  留 %4d页 %8.1fMB  %s" % (keep[0], keep[1] / 1024 ** 2, os.path.basename(keep[2])[:52]))
        print("  删 %4d页 %8.1fMB  %s" % (n, sz / 1024 ** 2, os.path.basename(p)[:52]))
        print()

    if not apply:
        print("（加 --apply 才删）")
        return

    ok = freed = 0
    log = open(r"E:\desktop\书库盘点\删除_同名少版本.csv", "w", encoding="utf-8-sig")
    log.write("删除的文件,页数,大小MB,保留的文件,保留页数\n")
    for k, keep, (n, sz, p) in plan:
        try:
            os.remove(p)
            ok += 1
            freed += sz
            log.write("%s,%d,%.1f,%s,%d\n" % (os.path.relpath(p, ROOT), n, sz / 1024 ** 2,
                                              os.path.relpath(keep[2], ROOT), keep[0]))
        except Exception as e:
            print("  删失败 %s %s" % (os.path.basename(p)[:40], e))
    log.close()
    print("已删 %d 个，释放 %.1f MB" % (ok, freed / 1024 ** 2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
