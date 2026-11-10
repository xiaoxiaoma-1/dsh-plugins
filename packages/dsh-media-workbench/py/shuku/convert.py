# -*- coding: utf-8 -*-
"""把非 PDF 的电子书转成 PDF（纯文本流，可检索）。默认 dry-run。

- .docx  → python-docx 抽文字
- .doc   → Word COM 另存 HTML 再抽文字
- .epub  → 解析 zip 里的 xhtml 抽文字
- .txt   → 直接读
- .mobi/.ebk3/.djvu/.chm → 跳过（没有可靠离线转换器）

原文不删：转换成功后移进同目录的 `_原格式/`，随时可回退。
"""
import html
import os
import re
import sys

import fitz

ROOT = r"E:\wengao"
FONTS = [r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simsun.ttc"]
FONT = next((f for f in FONTS if os.path.exists(f)), None)


def strip_tags(s):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h[1-6]>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", "", s)
    return html.unescape(s)


def text_of_docx(p):
    import docx
    d = docx.Document(p)
    parts = [x.text for x in d.paragraphs if x.text.strip()]
    for t in d.tables:
        for row in t.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(parts)


_WORD = {"app": None}


def _word():
    if _WORD["app"] is None:
        import win32com.client as w
        app = w.Dispatch("Word.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        _WORD["app"] = app
    return _WORD["app"]


def text_of_doc(p):
    """先试 Word COM；Word 挂了就退回二进制 UTF-16 抽取（够读，格式会乱）。"""
    import tempfile
    try:
        app = _word()
        tmp = os.path.join(tempfile.gettempdir(), "kb_doc2txt.html")
        doc = None
        try:
            doc = app.Documents.Open(p, ReadOnly=True)
            doc.SaveAs(tmp, 8)  # wdFormatHTML
        finally:
            if doc is not None:
                try:
                    doc.Close(False)
                except Exception:
                    pass
        with open(tmp, "r", encoding="utf-8", errors="ignore") as f:
            return strip_tags(f.read())
    except Exception:
        return doc_binary_text(p)


CJK = r"\u4e00-\u9fa5"


def doc_binary_text(p):
    """.doc 里中文正文按 UTF-16LE 存，按「含 3 个以上汉字的长串」捞出来。"""
    raw = open(p, "rb").read()
    t = raw.decode("utf-16-le", errors="ignore")
    runs = re.findall(r"[%s，。！？、：；“”‘’（）《》A-Za-z0-9\-—…\.\s]{6,}" % CJK, t)
    keep = []
    for r in runs:
        if len(re.findall(r"[%s]" % CJK, r)) >= 3:
            keep.append(r.strip())
    return "\n".join(keep)


def text_of_epub(p):
    import zipfile
    out = []
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        # 按 spine 顺序尽量取，取不到就按文件名排序
        root = None
        if "META-INF/container.xml" in names:
            c = z.read("META-INF/container.xml").decode("utf-8", "ignore")
            m = re.search(r'full-path="([^"]+)"', c)
            if m:
                root = m.group(1)
        order = []
        if root and root in names:
            opf = z.read(root).decode("utf-8", "ignore")
            ids = re.findall(r'<itemref[^>]+idref="([^"]+)"', opf)
            base = os.path.dirname(root)
            man = dict(re.findall(r'<item[^>]+id="([^"]+)"[^>]+href="([^"]+)"', opf))
            man.update({k: v for v, k in re.findall(r'<item[^>]+href="([^"]+)"[^>]+id="([^"]+)"', opf)})
            for i in ids:
                h = man.get(i)
                if h:
                    order.append(os.path.join(base, h).replace("\\", "/"))
        if not order:
            order = [n for n in names if n.lower().endswith((".xhtml", ".html", ".htm"))]
        for n in order:
            n = n.lstrip("/")
            if n not in names:
                continue
            txt = strip_tags(z.read(n).decode("utf-8", "ignore"))
            if txt.strip():
                out.append(txt)
    return "\n".join(out)


def text_of(p, ext):
    if ext in (".txt",):
        for enc in ("utf-8", "gbk", "utf-16"):
            try:
                with open(p, "r", encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    if ext == ".docx":
        return text_of_docx(p)
    if ext == ".doc":
        return text_of_doc(p)
    if ext == ".epub":
        return text_of_epub(p)
    return None


def make_pdf(text, out_path, title=""):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise RuntimeError("没有文字")
    doc = fitz.open()
    W, H, M = 595, 842, 56           # A4
    per_page = 1500
    page = None
    y = 0
    size = 10.5
    line_h = size * 1.75
    for start in range(0, len(text), per_page):
        chunk = text[start:start + per_page]
        page = doc.new_page(width=W, height=H)
        if title and start == 0:
            page.insert_text((M, 46), title[:60], fontsize=15,
                             fontfile=FONT, fontname="china-s")
            y = 46 + 22
        else:
            y = M
        rect = fitz.Rect(M, y, W - M, H - M)
        rc = page.insert_textbox(rect, chunk, fontsize=size, fontfile=FONT,
                                 fontname="china-s", lineheight=1.5, align=0)
        if rc < 0:  # 放不下，退到下一页重排（简单处理：缩小重试一次）
            page.insert_textbox(rect, chunk[:int(len(chunk) * 0.85)], fontsize=size - 0.5,
                                fontfile=FONT, fontname="china-s", lineheight=1.4)
    doc.save(out_path, deflate=True)
    doc.close()


def main():
    apply = "--apply" in sys.argv
    exts = (".docx", ".doc", ".epub", ".txt")
    todo = []
    for dirpath, _, files in os.walk(ROOT):
        if "_原格式" in dirpath or "_已解压" in dirpath:
            continue
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext in exts:
                todo.append((os.path.join(dirpath, fn), ext))
    todo.sort()
    print("待转 %d 个" % len(todo))
    ok = fail = 0
    for p, ext in todo:
        out = os.path.splitext(p)[0] + ".pdf"
        if os.path.exists(out) and os.path.getsize(out) > 1024:
            print("  跳过（已有PDF）", os.path.basename(p)[:50])
            continue
        if not apply:
            print("  [试算] %-6s %s" % (ext, os.path.basename(p)[:60]))
            continue
        try:
            t = text_of(p, ext)
            make_pdf(t, out, os.path.splitext(os.path.basename(p))[0])
            # 原文移进 _原格式
            bak = os.path.join(os.path.dirname(p), "_原格式")
            os.makedirs(bak, exist_ok=True)
            os.replace(p, os.path.join(bak, os.path.basename(p)))
            ok += 1
            print("  OK %-6s -> %s" % (ext, os.path.basename(out)[:58]))
        except Exception as e:
            fail += 1
            print("  失败 %-6s %s | %s" % (ext, os.path.basename(p)[:40], str(e)[:70]))
    print("完成：成功 %d，失败 %d" % (ok, fail))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
