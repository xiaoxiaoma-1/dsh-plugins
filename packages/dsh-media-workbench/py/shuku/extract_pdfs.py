# -*- coding: utf-8 -*-
"""从压缩包里抽出 PDF（只要 PDF，视频音频丢弃）。默认 dry-run，--apply 才解压。

加密包读不出来 → 记入"缺密码"清单，不动它。
抽出的文件落在压缩包同级目录：<包名去掉扩展名>_已解压\
"""
import os
import sys
import zipfile

ROOT = r"E:\wengao"
OUT = r"E:\desktop\书库盘点"


def is_encrypted(zf):
    for e in zf.infolist():
        if e.is_dir():
            continue
        try:
            with zf.open(e) as s:
                s.read(1)
            return False
        except Exception:
            return True
    return False


def main():
    apply = "--apply" in sys.argv
    zips = []
    for dirpath, _, files in os.walk(ROOT):
        for fn in files:
            if fn.lower().endswith(".zip"):
                zips.append(os.path.join(dirpath, fn))
    zips.sort(key=lambda p: -os.path.getsize(p))

    total_pdf = 0
    total_pdf_bytes = 0
    lines = []
    for z in zips:
        size_mb = os.path.getsize(z) / 1024 ** 2
        try:
            zf = zipfile.ZipFile(z)
        except Exception as e:
            lines.append("[打不开] %s (%s)" % (z, e))
            continue
        try:
            enc = is_encrypted(zf)
            pdfs = [e for e in zf.infolist() if e.filename.lower().endswith(".pdf")]
            n_all = len(zf.infolist())
            bytes_pdf = sum(e.file_size for e in pdfs)
            head = "[%s] %6.0f MB  %d 条目  内含 PDF %d 个 (%.0f MB)" % (
                "加密" if enc else "可解", size_mb, n_all, len(pdfs), bytes_pdf / 1024 ** 2)
            lines.append(head + "  " + os.path.relpath(z, ROOT)[:70])
            if enc or not pdfs:
                continue
            total_pdf += len(pdfs)
            total_pdf_bytes += bytes_pdf
            if apply:
                dst_root = os.path.join(os.path.dirname(z),
                                        os.path.splitext(os.path.basename(z))[0] + "_已解压")
                ok = 0
                for e in pdfs:
                    # 去掉包内顶层冗余目录，保留书名结构
                    name = e.filename.replace("\\", "/")
                    parts = [p for p in name.split("/") if p and p not in (".", "..")]
                    dst = os.path.join(dst_root, *parts)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    try:
                        with zf.open(e) as s, open(dst, "wb") as f:
                            while True:
                                b = s.read(1 << 20)
                                if not b:
                                    break
                                f.write(b)
                        ok += 1
                    except Exception as ex:
                        lines.append("   [抽失败] %s %s" % (e.filename[:60], ex))
                lines.append("   → 已抽出 %d 个 PDF 到 %s" % (ok, dst_root))
        finally:
            zf.close()

    print("\n".join(lines))
    print("\n可抽 PDF 合计 %d 个 / %.0f MB" % (total_pdf, total_pdf_bytes / 1024 ** 2))
    if not apply:
        print("（加 --apply 才真解压）")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
