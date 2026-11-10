# -*- coding: utf-8 -*-
"""抽 PDF（第二版）：带密码的加密包也能抽。密码取自 zip密码.txt。"""
import os
import sys
import zipfile

ROOT = r"E:\wengao"
PWDFILE = r"E:\desktop\书库盘点\zip密码.txt"


def load_pwds():
    d = {}
    if os.path.exists(PWDFILE):
        for line in open(PWDFILE, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or "\t" not in line:
                continue
            pwd, path = line.split("\t", 1)
            d[os.path.basename(path)] = pwd
    return d


def main():
    apply = "--apply" in sys.argv
    pwds = load_pwds()
    total = 0
    done = 0
    for dirpath, _, files in os.walk(ROOT):
        if "_已解压" in dirpath or "_原格式" in dirpath:
            continue
        for fn in sorted(files):
            if not fn.lower().endswith(".zip"):
                continue
            p = os.path.join(dirpath, fn)
            pwd = pwds.get(fn)
            try:
                zf = zipfile.ZipFile(p)
            except Exception as e:
                print("  打不开 %s %s" % (fn[:40], e))
                continue
            pdfs = [e for e in zf.infolist() if e.filename.lower().endswith(".pdf")]
            if not pdfs:
                zf.close()
                continue
            enc = any(e.flag_bits & 0x1 for e in pdfs)
            print("%-46s 加密=%-5s 密码=%-12s PDF=%d" % (fn[:46], enc, pwd or "-", len(pdfs)))
            if enc and not pwd:
                zf.close()
                continue
            total += len(pdfs)
            if apply:
                dst_root = os.path.join(dirpath, os.path.splitext(fn)[0] + "_已解压")
                ok = 0
                for e in pdfs:
                    parts = [x for x in e.filename.replace("\\", "/").split("/") if x and x not in (".", "..")]
                    dst = os.path.join(dst_root, *parts)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    try:
                        with zf.open(e, pwd=pwd.encode("utf-8") if pwd else None) as s, open(dst, "wb") as f:
                            while True:
                                b = s.read(1 << 20)
                                if not b:
                                    break
                                f.write(b)
                        ok += 1
                    except Exception as ex:
                        print("    抽失败 %s %s" % (e.filename[:44], str(ex)[:50]))
                print("    → 抽出 %d / %d 个" % (ok, len(pdfs)))
                done += ok
            zf.close()
    print("\n合计可抽 %d 个 PDF%s" % (total, ("，本次抽出 %d 个" % done) if apply else "（加 --apply 才抽）"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
