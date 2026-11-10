# -*- coding: utf-8 -*-
"""doc / docx / txt / epub 直接出 Markdown 入库（不经过 PDF）。

用户说得对：这些本来就是文字，转 PDF 再抽回来是白绕一圈。
用法：python direct_md.py [--apply]
"""
import datetime
import html
import os
import re
import sqlite3
import sys
import uuid
import zipfile

ROOT = r"E:\wengao"
MD_DIR = r"E:\wengao_md"
DB = r"E:\desktop\media\workbench.db"

HEAD2 = re.compile(r"^(第[一二三四五六七八九十百零〇\d]+[章节篇回卷部]|【.+?】|前言|序言?|目录|后记|附录)")
CHAP = re.compile(r"^(第[一二三四五六七八九十百零〇\d]+[章节篇回卷部][^\n]{0,40})$")


def chunk_text(paras, lo=500, hi=900):
    chunks, cur = [], []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if cur and (sum(len(x) for x in cur) >= lo or CHAP.match(p)):
            chunks.append(cur)
            cur = []
        cur.append(p)
        if sum(len(x) for x in cur) >= hi:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def ingest(name, paras, ext):
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    row = c.execute("select id from books where title=?", (name,)).fetchone()
    if row:
        bid = row[0]
        c.execute("delete from chunks_fts where book_id=?", (bid,))
        c.execute("delete from book_chunks where book_id=?", (bid,))
    else:
        bid = "book_" + uuid.uuid4().hex[:10]
        c.execute("insert into books(id,title,ocr_state,created_at) values(?,?,'done',?)",
                  (bid, name, datetime.datetime.now().isoformat(timespec="seconds")))
    now = datetime.datetime.now().isoformat(timespec="seconds")
    chunks = chunk_text(paras)
    n = 0
    for i, parts in enumerate(chunks):
        content = "\n\n".join(parts).strip()
        if len(content) < 20:
            continue
        heading = ""
        if CHAP.match(content.split("\n")[0]):
            heading = content.split("\n")[0][:40]
        cid = "%s_c%04d" % (bid, i)
        c.execute("insert into book_chunks(id,book_id,page_from,page_to,heading,content,chars,created_at)"
                  " values(?,?,?,?,?,?,?,?)", (cid, bid, 0, 0, heading, content, len(content), now))
        tok = " ".join(ch for ch in content if not ch.isspace())
        c.execute("insert into chunks_fts(tok,content,book_id,page_from) values(?,?,?,?)",
                  (tok, content, bid, 0))
        n += 1
    c.execute("update books set ocr_state='done' where id=?", (bid,))
    c.commit()
    c.close()
    return n


def strip_tags(s):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h[1-6]>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", "", s)
    return html.unescape(s)


_word = {"app": None}


def text_doc(p):
    import tempfile
    try:
        import win32com.client as w
        if _word["app"] is None:
            app = w.Dispatch("Word.Application")
            app.Visible = False
            app.DisplayAlerts = 0
            _word["app"] = app
        tmp = os.path.join(tempfile.gettempdir(), "kb_direct.html")
        d = _word["app"].Documents.Open(p, ReadOnly=True)
        try:
            d.SaveAs(tmp, 8)
        finally:
            d.Close(False)
        return strip_tags(open(tmp, encoding="utf-8", errors="ignore").read())
    except Exception:
        raw = open(p, "rb").read()
        t = raw.decode("utf-16-le", errors="ignore")
        runs = re.findall(r"[\u4e00-\u9fa5，。！？、：；“”（）《》A-Za-z0-9\-—…\.\s]{6,}", t)
        return "\n".join(r.strip() for r in runs
                         if len(re.findall(r"[\u4e00-\u9fa5]", r)) >= 3)


def text_docx(p):
    import docx
    d = docx.Document(p)
    out = [x.text for x in d.paragraphs if x.text.strip()]
    for t in d.tables:
        for row in t.rows:
            out.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n\n".join(out)


def text_epub(p):
    out = []
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        root = None
        if "META-INF/container.xml" in names:
            c = z.read("META-INF/container.xml").decode("utf-8", "ignore")
            m = re.search(r'full-path="([^"]+)"', c)
            if m:
                root = m.group(1)
        order = []
        if root and root in names:
            opf = z.read(root).decode("utf-8", "ignore")
            base = os.path.dirname(root)
            man = {}
            for m in re.finditer(r"<item\b[^>]*>", opf):
                tag = m.group(0)
                i = re.search(r'id="([^"]+)"', tag)
                h = re.search(r'href="([^"]+)"', tag)
                if i and h:
                    man[i.group(1)] = h.group(1)
            for m in re.finditer(r'<itemref[^>]*idref="([^"]+)"', opf):
                h = man.get(m.group(1))
                if h:
                    order.append(os.path.normpath(os.path.join(base, h)).replace("\\", "/"))
        if not order:
            order = [n for n in names if n.lower().endswith((".xhtml", ".html", ".htm"))]
        for n in order:
            if n not in names:
                continue
            t = strip_tags(z.read(n).decode("utf-8", "ignore")).strip()
            if t:
                out.append(t)
    return "\n\n".join(out)


def text_txt(p):
    for enc in ("utf-8", "gbk", "utf-16", "utf-8-sig"):
        try:
            return open(p, encoding=enc).read()
        except UnicodeDecodeError:
            continue
    return open(p, encoding="utf-8", errors="ignore").read()


def get_text(p, ext):
    return {".docx": text_docx, ".doc": text_doc, ".epub": text_epub, ".txt": text_txt}[ext](p)


def main():
    apply = "--apply" in sys.argv
    files = []
    for dp, _, fs in os.walk(ROOT):
        for f in fs:
            ext = os.path.splitext(f)[1].lower()
            if ext in (".docx", ".doc", ".epub", ".txt"):
                files.append((os.path.join(dp, f), ext))
    files.sort()
    print("待处理 %d 个（doc/docx/epub/txt）" % len(files))

    ok = fail = 0
    for p, ext in files:
        name = os.path.splitext(os.path.basename(p))[0]
        try:
            t = get_text(p, ext)
            paras = [x.strip() for x in re.split(r"\n{1,}", t) if x.strip()]
            nchar = sum(len(x) for x in paras)
            if nchar < 100:
                print("  跳过（内容太少 %d 字） %s" % (nchar, name[:44]))
                continue
            if not apply:
                print("  [试算] %-5s %6d 字  %s" % (ext, nchar, name[:50]))
                ok += 1
                continue
            md = "# " + name + "\n\n> 来源：" + ext[1:].upper() + " 直接提取（未转 PDF、未 OCR）。\n\n" + "\n\n".join(paras)
            os.makedirs(MD_DIR, exist_ok=True)
            open(os.path.join(MD_DIR, name + ".md"), "w", encoding="utf-8").write(md)
            n = ingest(name, paras, ext)
            ok += 1
            print("  OK %-5s %6d 字 %3d 块  %s" % (ext, nchar, n, name[:44]))
        except Exception as e:
            fail += 1
            print("  失败 %-5s %s | %s" % (ext, name[:40], str(e)[:80]))

    print("\n完成：%d 个，失败 %d" % (ok, fail))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
