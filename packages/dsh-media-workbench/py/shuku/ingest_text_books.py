# -*- coding: utf-8 -*-
"""把磁盘上「有文字层的 PDF」和「EPUB」直接入库，不用等 OCR。

背景：ocr_daemon.py 只处理纯扫描件 PDF（前两页抽不出文字的），
另外那一大批有文字层的 PDF 和全部 EPUB 从来没进过库。
书库一直在 1685 本，不是因为没文件，是因为入库流水线只走了扫描件那一路。

用法：
    python ingest_text_books.py --dry 10    只看前 10 个怎么解析，不入库
    python ingest_text_books.py --go        全量入库
"""
import argparse
import hashlib
import os
import re
import sqlite3
import sys
import time

LIB = r"E:\wengao"
DB = r"E:\desktop\media\workbench.db"
LOG = r"E:\desktop\书库盘点\ingest_text.log"


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def clean_name(name):
    """从文件名里剥出版本号、括号注释、广告尾巴。"""
    n = os.path.splitext(os.path.basename(name))[0]
    n = re.sub(r"[（(][^）)]*(微信|bcl|公众号|更多课程)[^）)]*[）)]", "", n)
    n = re.sub(r"_\d{5,}$", "", n)                     # 女人的性爱动机_13569013
    n = re.sub(r"[-_\s]*\d{6,}$", "", n)
    n = re.sub(r"[\s\-_]+$", "", n)
    return n.strip() or os.path.splitext(os.path.basename(name))[0]


def book_id_for(path):
    return "bk_" + hashlib.md5(os.path.normcase(os.path.abspath(path)).encode("utf-8")).hexdigest()[:14]


# ---------- 抽取 ----------

def read_pdf(path):
    """返回 [(page_no, text)]，抽不出文字就返回空"""
    try:
        import pypdf
        out = []
        r = pypdf.PdfReader(path)
        for i, pg in enumerate(r.pages):
            try:
                t = (pg.extract_text() or "").strip()
            except Exception:
                t = ""
            if t:
                out.append((i + 1, t))
        return out
    except Exception:
        return []


def read_epub(path):
    """返回 [(spine_idx, text)]，按章节顺序"""
    try:
        from ebooklib import epub, ITEM_DOCUMENT
    except ImportError:
        return None, "没装 ebooklib"
    import zipfile
    from html.parser import HTMLParser

    class Strip(HTMLParser):
        def __init__(self):
            super().__init__()
            self.buf = []
            self.skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                self.skip += 1
            elif tag in ("p", "br", "div", "h1", "h2", "h3", "li"):
                self.buf.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style") and self.skip:
                self.skip -= 1

        def handle_data(self, data):
            if not self.skip:
                self.buf.append(data)

        def text(self):
            return "".join(self.buf)

    out = []
    try:
        z = zipfile.ZipFile(path)
        names = [n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))]
        names.sort()
        for idx, n in enumerate(names):
            raw = z.read(n).decode("utf-8", "replace")
            p = Strip()
            p.feed(raw)
            t = re.sub(r"\n{3,}", "\n\n", p.text()).strip()
            if len(t) > 100:
                out.append((idx + 1, t))
        z.close()
    except Exception as e:
        return None, str(e)[:60]
    return out, None


# ---------- 切块入��� ----------

def chunk_text(pages, size=1200):
    buf, out = "", []
    for pno, t in pages:
        buf += "\n[page %d]\n" % pno + t
        while len(buf) >= size:
            out.append(buf[:size])
            buf = buf[size:]
    if buf.strip():
        out.append(buf)
    return out


def ingest(conn, path, title, blocks, kind):
    cur = conn.cursor()
    bid = book_id_for(path)
    cur.execute("select 1 from books where id=?", (bid,))
    if cur.fetchone():
        return 0, "已存在"
    cur.execute("""insert or replace into books(id,title,source_path,pages,ocr_state,quality,created_at)
                   values(?,?,?,?,?,?,datetime('now'))""",
                (bid, title, os.path.abspath(path), len(blocks), "done", kind))
    n = 0
    for chunk in blocks:
        n += 1
        cur.execute("""insert or replace into book_chunks(id,book_id,page_from,content)
                       values(?,?,?,?)""",
                    ("%s_c%04d" % (bid, n), bid, n, chunk))
    return n, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", type=int, default=0, help="只试前 N 个，不入库")
    ap.add_argument("--go", action="store_true", help="全量入库")
    args = ap.parse_args()
    if not args.dry and not args.go:
        print("用 --dry N 或 --go")
        return

    conn = sqlite3.connect(DB, timeout=180)
    conn.execute("pragma busy_timeout = 180000")

    known = set()
    for r in conn.execute("select source_path, title from books"):
        if r[0]:
            known.add(os.path.normcase(os.path.abspath(r[0])))
        if r[1]:
            known.add(os.path.splitext(r[1])[0].strip().lower())

    todo = []
    for dp, _, fs in os.walk(LIB):
        if "_已解压" in dp or "_原格式" in dp:
            continue
        for f in fs:
            low = f.lower()
            if not low.endswith((".pdf", ".epub")):
                continue
            p = os.path.join(dp, f)
            base = os.path.splitext(f)[0].strip()
            if os.path.normcase(os.path.abspath(p)) in known:
                continue
            if base.lower() in known:
                continue
            if os.path.splitext(base)[0].lower() in known:   # 去掉 _13569013 这类尾巴后再比
                continue
            todo.append(p)

    log("待处理文件: %d 个（pdf+epub，且未入库）" % len(todo))
    if args.dry:
        todo = todo[:args.dry]

    t0 = time.time()
    stat = {"pdf_ok": 0, "epub_ok": 0, "pdf_scan": 0, "fail": 0, "skip": 0, "blocks": 0}
    for i, p in enumerate(todo, 1):
        name = clean_name(p)
        try:
            if p.lower().endswith(".epub"):
                pages, err = read_epub(p)
                kind = "epub"
            else:
                pages = read_pdf(p)
                err = None
                kind = "pdf-text"
            if err:
                log("  ✗ %s | %s" % (name[:36], err)); stat["fail"] += 1; continue
            if not pages or sum(len(t) for _, t in pages) < 500:
                stat["pdf_scan"] += 1
                if args.dry:
                    log("  ⊘ %s | 没文字层（留给 OCR）" % name[:36])
                continue
            blocks = chunk_text(pages)
            if args.dry:
                log("  ✓ %s | %d 页 → %d 块 | 首块: %s" %
                    (name[:36], len(pages), len(blocks), blocks[0][:60].replace("\n", " ")))
                stat[kind.replace("-", "_").replace("epub", "epub") if kind != "epub" else "epub_ok"] = \
                    stat.get("epub_ok" if kind == "epub" else "pdf_ok", 0)
                continue
            n, why = ingest(conn, p, name, blocks, kind)
            if why:
                stat["skip"] += 1
            else:
                stat["epub_ok" if kind == "epub" else "pdf_ok"] += 1
                stat["blocks"] += n
            if i % 25 == 0:
                conn.commit()
                log("  进度 %d/%d | 已入 %d 本 %d 块 | %.1f 分钟" %
                    (i, len(todo), stat["pdf_ok"] + stat["epub_ok"], stat["blocks"], (time.time() - t0) / 60))
        except Exception as e:
            stat["fail"] += 1
            if args.dry:
                log("  ✗ %s | %s" % (name[:36], str(e)[:60]))
    conn.commit()

    print("\n=== 结果 ===")
    print("  PDF(文字层) 入库: %d" % stat["pdf_ok"])
    print("  EPUB 入库: %d" % stat["epub_ok"])
    print("  无文字层(留给OCR): %d" % stat["pdf_scan"])
    print("  失败: %d | 跳过: %d" % (stat["fail"], stat["skip"]))
    print("  新增块: %d" % stat["blocks"])
    print("  用��� %.1f 分钟" % ((time.time() - t0) / 60))
    print("  书库现有: %d 本" % conn.execute("select count(*) from books").fetchone()[0])
    conn.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
