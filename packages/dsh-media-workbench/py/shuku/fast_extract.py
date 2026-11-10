# -*- coding: utf-8 -*-
"""快路径：有文字层的 PDF 直接抽文本 -> Markdown -> 切块入库（不跑 OCR）。

用法：
  python fast_extract.py            # 只跑文字层
  python fast_extract.py --dry      # 只统计不动
  python fast_extract.py --limit 50 # 限本数

扫描件（无文字层）会被跳过，留给 OCR 队列。
"""
import datetime
import os
import re
import sqlite3
import sys
import time
import uuid

import fitz

ROOT = r"E:\wengao"
MD_DIR = r"E:\wengao_md"
DB = r"E:\desktop\media\workbench.db"

HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")
HEAD2 = re.compile(r"^(第[一二三四五六七八九十百零〇\d]+[章节篇回卷部]|【.+?】|前言|序言?|目录|后记|附录)")


def chunk_pages(pages, lo=500, hi=900):
    chunks, cur, pfrom = [], [], None
    for pno, body in pages:
        head = body.startswith("#")
        if cur and (sum(len(x[1]) for x in cur) >= lo or head):
            chunks.append((pfrom, cur[-1][0], cur))
            cur, pfrom = [], None
        if not cur:
            pfrom = pno
        cur.append((pno, body))
        if sum(len(x[1]) for x in cur) >= hi:
            chunks.append((pfrom, pno, cur))
            cur, pfrom = [], None
    if cur:
        chunks.append((pfrom, cur[-1][0], cur))
    return chunks


def ingest(name, chunks, pages_n):
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
    n = 0
    for i, (a, b, parts) in enumerate(chunks):
        content = "\n\n".join(t for _, t in parts).strip()
        if len(content) < 20:
            continue
        heading = ""
        m = HEAD_RE.match(content.split("\n")[0])
        if m:
            heading = m.group(2)[:40]
        cid = "%s_c%04d" % (bid, i)
        c.execute("insert into book_chunks(id,book_id,page_from,page_to,heading,content,chars,created_at)"
                  " values(?,?,?,?,?,?,?,?)", (cid, bid, a, b, heading, content, len(content), now))
        tok = " ".join(ch for ch in content if not ch.isspace())
        c.execute("insert into chunks_fts(tok,content,book_id,page_from) values(?,?,?,?)",
                  (tok, content, bid, a))
        n += 1
    c.execute("update books set pages=?, ocr_state='done' where id=?", (pages_n, bid))
    c.commit()
    c.close()
    return bid, n


def text_pages(pdf):
    """返回 [(页码, 文本)]；顺带判断是否文字层（每页平均汉字 >= 150 才算）。"""
    d = fitz.open(pdf)
    try:
        n = d.page_count
        idx = sorted({0, n // 4, n // 2, n * 3 // 4, n - 1} & set(range(n))) if n > 1 else [0]
        probe_chars = sum(len(d[i].get_text("text").strip()) for i in idx)
        if not idx or probe_chars < 150 * len(idx):
            return None, n
        pages = []
        for i in range(n):
            t = d[i].get_text("text").strip()
            if len(t) >= 30:
                pages.append((i + 1, t))
        if not pages:
            return None, n
        return pages, n
    finally:
        d.close()


def build_md(name, pages):
    out = ["# " + name, "", "> 来源：文字版 PDF 直接抽取（未 OCR）。", ""]
    for pno, t in pages:
        first = t.split("\n")[0].strip()
        if HEAD2.match(first):
            out.append("## " + first)
            rest = "\n".join(t.split("\n")[1:]).strip()
            if rest:
                out.append(rest)
        else:
            out.append(t)
        out.append("<!-- p.%d -->" % pno)
    return "\n\n".join(out)


def main():
    dry = "--dry" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    pdfs = []
    for dp, _, fs in os.walk(ROOT):
        if "_已解压" in dp or "_原格式" in dp:
            continue
        for f in fs:
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(dp, f))
    pdfs.sort(key=lambda p: os.path.getmtime(p))

    done = set()
    try:
        c = sqlite3.connect(DB)
        done = {r[0] for r in c.execute("select title from books where ocr_state='done'")}
        c.close()
    except Exception:
        pass

    NOVEL = re.compile(r"(小说|言情|穿越|重生|总裁|宫斗|嫡女|庶女|招摇|锦绣良缘|天子谋|谋天子|首席幕僚|省长亲信|再嫁|掌上明珠|琅琊|甄嬛|凤囚凰|醉玲珑|青坼|宋明风云|苍壁书|典藏|套装全[0-9]+册)")
    KEEP = re.compile(r"(遥远的救世主|豆豆|许荣哲)")
    todo = [p for p in pdfs
            if os.path.splitext(os.path.basename(p))[0] not in done
            and not (NOVEL.search(os.path.basename(p)) and not KEEP.search(os.path.basename(p)))]
    print("PDF %d 本，已入库 %d 本，待处理 %d 本" % (len(pdfs), len(done), len(todo)), flush=True)

    ok = skip = fail = 0
    t0 = time.time()
    for i, p in enumerate(todo, 1):
        name = os.path.splitext(os.path.basename(p))[0]
        try:
            pages, n = text_pages(p)
        except Exception as e:
            fail += 1
            print("  [%d] 打不开 %s | %s" % (i, name[:40], str(e)[:60]), flush=True)
            continue
        if pages is None:
            skip += 1
            continue
        chars = sum(len(t) for _, t in pages)
        if dry:
            print("  [%d] 文字层 %5d 页 %8d 字  %s" % (i, n, chars, name[:44]), flush=True)
            ok += 1
            if limit and ok >= limit:
                break
            continue
        md = build_md(name, pages)
        os.makedirs(MD_DIR, exist_ok=True)
        open(os.path.join(MD_DIR, name + ".md"), "w", encoding="utf-8").write(md)
        sents = re.split(r"\n\n", md)
        pg = []
        for blk in sents:
            m = re.search(r"<!-- p\.(\d+) -->", blk)
            pno = int(m.group(1)) if m else (pg[-1][0] if pg else 1)
            body = re.sub(r"<!--.*?-->", "", blk).strip()
            if body:
                pg.append((pno, body))
        bid, nchunk = ingest(name, chunk_pages(pg), n)
        ok += 1
        print("  [%d] OK %4d 页 %7d 字 %3d 块  %s" % (i, n, chars, nchunk, name[:40]), flush=True)
        if limit and ok >= limit:
            break

    print("\n完成：入库 %d 本，跳过（扫描件）%d 本，失败 %d 本，用时 %.1f 分钟"
          % (ok, skip, fail, (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
