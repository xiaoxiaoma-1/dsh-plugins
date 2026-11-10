# -*- coding: utf-8 -*-
"""把情感/关系操控类书归到 _分类\\情感与关系\\，并清掉文件名噪声。默认 dry-run。"""
import csv
import os
import re
import shutil
import sys

ROOT = r"E:\wengao"
DST = os.path.join(ROOT, "_分类", "情感与关系")
INDEX = os.path.join(ROOT, "_分类", "_索引_情感与关系.csv")

KW = ["坏男人", "好男人病毒", "迷魂阵", "看穿女人心", "爱情阴谋论", "极端自我", "ji端自我",
      "把妹", "搭讪", "PUA", "情感操控", "制服小人", "奸的好人", "不要脸", "备胎", "渣男",
      "情感勒索", "勾hun", "勾魂", "心锚", "催眠", "情场", "情欲", "qing场", "qing欲",
      "让她无法离开", "男人要的不是", "财se", "财色", "炼丹", "心魔xing销", "xi脑", "洗脑",
      "mou权手duan", "权mou兵法", "NLP", "印象xi", "出位"]
NOISE = re.compile(r"[（(](无水印|防封版|防和谐|不防封版|加密防封|完整版)[）)]|（无水印）|\s{2,}")


def clean(name):
    base, ext = os.path.splitext(name)
    base = NOISE.sub("", base)
    base = re.sub(r"[-_—\s]+$", "", base).strip()
    return base + ext


def main():
    apply = "--apply" in sys.argv
    hits = []
    for dp, dn, fs in os.walk(ROOT):
        if "_原格式" in dp or "_已解压" in dp or "_分类" in dp:
            continue
        for f in fs:
            if not f.lower().endswith((".pdf", ".epub", ".mobi", ".doc", ".docx", ".txt")):
                continue
            if any(k.lower() in f.lower() for k in KW):
                hits.append(os.path.join(dp, f))

    hits.sort()
    rows = []
    print("命中 %d 个，目标目录 %s" % (len(hits), DST))
    for p in hits:
        new = clean(os.path.basename(p))
        dst = os.path.join(DST, new)
        # 重名加序号
        if os.path.exists(dst):
            stem, ext = os.path.splitext(new)
            i = 2
            while os.path.exists(os.path.join(DST, "%s_%d%s" % (stem, i, ext))):
                i += 1
            dst = os.path.join(DST, "%s_%d%s" % (stem, i, ext))
        rows.append([os.path.relpath(p, ROOT), os.path.relpath(dst, ROOT),
                     round(os.path.getsize(p) / 1024 ** 2, 1)])
        print("  %8.1f MB  %s" % (rows[-1][2], os.path.basename(p)[:70]))

    if not apply:
        print("\n（加 --apply 才移动）")
        return

    os.makedirs(DST, exist_ok=True)
    moved = 0
    with open(INDEX, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["原路径", "新路径", "大小MB"])
        for old_rel, new_rel, mb in rows:
            old = os.path.join(ROOT, old_rel)
            new = os.path.join(ROOT, new_rel)
            try:
                shutil.move(old, new)
                w.writerow([old_rel, new_rel, mb])
                moved += 1
            except Exception as e:
                print("  移动失败:", old_rel[:60], e)
    print("已移动 %d 个 → %s" % (moved, DST))
    print("索引：", INDEX)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
