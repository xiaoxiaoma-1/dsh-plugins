# -*- coding: utf-8 -*-
"""书库清理：默认只算不删（dry-run），加 --apply 才真删。

删三类：
 A 重复（哈希一致，同名同大小多份）→ 保留一份
 B 同一本书多格式 → 只留 PDF（没有 PDF 就留最大的）
 C 垃圾 txt（解压密码/付费必读/参考链接）
 D 音视频独立文件（用户：只留书）
不删：压缩包（zip/rar/7z 里混着 PDF，需先解压抽书）、图片、其他
"""
import csv
import hashlib
import os
import re
import sys
from collections import defaultdict

ROOT = r"E:\wengao"
OUT = r"E:\desktop\书库盘点"


def norm(s):
    s = s.lower()
    s = re.sub(r"\.(pdf|epub|mobi|ebk3|azw3|djvu|chm|txt|docx?|mht|mhtml)$", "", s)
    s = re.sub(r"[（(\[【][^）)\]】]{0,20}[）)\]】]", "", s)
    s = re.sub(r"(全译本|完整版|修订版|精校版|高清版|扫描版|电子版|文字版|典藏版|珍藏版)", "", s)
    s = re.sub(r"[\s\.\-_·,，、:：;；'\"“”‘’]+", "", s)
    return s


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


JUNK_TXT = re.compile(r"(解压密码|付费学员必读|付费学员必看|不要在线解压|防封|防和谐|参考笔记链接|必读！)", re.I)


def main():
    apply = "--apply" in sys.argv
    books = list(csv.DictReader(open(os.path.join(OUT, "书目清单.csv"), encoding="utf-8-sig")))
    allf = list(csv.DictReader(open(os.path.join(OUT, "全量清单.csv"), encoding="utf-8-sig")))

    plan = []   # (类别, 路径, 大小MB, 说明)

    # ---------- A 重复 ----------
    by = defaultdict(list)
    for r in books:
        by[(norm(r["文件名"]), round(float(r["大小MB"]), 2))].append(r)
    hashed, groups = {}, []
    for k, v in by.items():
        if len(v) < 2:
            continue
        hs = defaultdict(list)
        for r in v:
            p = os.path.join(ROOT, r["相对路径"])
            if p not in hashed:
                try:
                    hashed[p] = md5(p)
                except OSError:
                    hashed[p] = None
            if hashed[p]:
                hs[hashed[p]].append(r)
        for h, same in hs.items():
            if len(same) > 1:
                groups.append(same)

    for same in groups:
        same.sort(key=lambda r: (len(r["相对路径"]), r["相对路径"]))
        for r in same[1:]:
            plan.append(("A重复", r["相对路径"], float(r["大小MB"]), "与 %s 相同" % same[0]["相对路径"][:40]))

    # ---------- B 多格式 ----------
    fg = defaultdict(list)
    for r in books:
        fg[norm(r["文件名"])].append(r)
    for k, v in fg.items():
        if len(v) < 2:
            continue
        exts = set(x["格式"].lower().lstrip(".") for x in v)
        if len(exts) < 2:
            continue
        v.sort(key=lambda x: -float(x["大小MB"]))
        keep = next((x for x in v if x["格式"].lower() == ".pdf"), v[0])
        for x in v:
            if x is keep:
                continue
            plan.append(("B多格式", x["相对路径"], float(x["大小MB"]), "同书留 %s" % keep["格式"]))

    # ---------- C 垃圾 txt ----------
    for r in books:
        if r["格式"].lower() == ".txt" and JUNK_TXT.search(r["文件名"]):
            plan.append(("C垃圾txt", r["相对路径"], float(r["大小MB"]), "解压密码/必读类"))

    # ---------- D 音视频 ----------
    for r in allf:
        if r["类型"] in ("video", "audio"):
            plan.append(("D音视频", r["相对路径"], float(r["大小MB"]), r["格式"]))

    # ---------- 汇总 ----------
    agg = defaultdict(lambda: [0, 0.0])
    for c, p, s, why in plan:
        agg[c][0] += 1
        agg[c][1] += s
    print("== 待删清单（%s）==" % ("执行" if apply else "试算，不会删"))
    for c in ("A重复", "B多格式", "C垃圾txt", "D音视频"):
        n, mb = agg[c]
        print("  %-8s %6d 个  %9.1f MB  (%.1f GB)" % (c, n, mb, mb / 1024))
    tot_mb = sum(v[1] for v in agg.values())
    print("  合计 %d 个 / %.1f GB" % (len(plan), tot_mb / 1024))

    # 落盘清单
    lp = os.path.join(OUT, "待删清单.csv")
    with open(lp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["类别", "相对路径", "大小MB", "说明"])
        for c, p, s, why in sorted(plan, key=lambda x: x[0]):
            w.writerow([c, p, s, why])
    print("清单已写：", lp)

    if not apply:
        print("\n（加 --apply 才会真删）")
        return

    ok = fail = 0
    freed = 0.0
    with open(os.path.join(OUT, "删除日志.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["类别", "路径", "大小MB", "结果"])
        for c, p, s, why in plan:
            full = os.path.join(ROOT, p)
            try:
                os.remove(full)
                ok += 1
                freed += s
                w.writerow([c, p, s, "已删"])
            except FileNotFoundError:
                fail += 1
                w.writerow([c, p, s, "不存在"])
            except OSError as e:
                fail += 1
                w.writerow([c, p, s, "失败:" + str(e)[:60]])
    print("已删 %d 个，失败 %d 个，释放约 %.1f GB" % (ok, fail, freed / 1024))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
