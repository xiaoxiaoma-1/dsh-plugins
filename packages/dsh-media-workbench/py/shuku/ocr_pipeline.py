# -*- coding: utf-8 -*-
"""扫描件 OCR 流水线：OCR 逐页 -> Markdown -> 切块入库（断点续跑）。

用法：
  python ocr_pipeline.py "12-【帝王之术】"          # 只跑名字含该关键字的
  python ocr_pipeline.py "12-【帝王之术】" --limit 5
跳过：已入库的书。每本书的 md 写 E:\wengao_md，OCR 原文写 E:\wengao_ocr。
"""
import datetime
import os
import re
import sqlite3
import sys
import time
import uuid

import fitz

# onnxruntime 的 CUDA 插件不会自动去找 site-packages/nvidia 下的 DLL，
# 必须在 import onnxruntime 之前把它们加进 DLL 搜索路径，否则会静默回落 CPU。
def _setup_cuda_dlls():
    import sysconfig
    sp = sysconfig.get_paths().get("purelib") or ""
    nv = os.path.join(sp, "nvidia")
    if not os.path.isdir(nv):
        return []
    added = []
    for sub in ("cublas/bin", "cudnn/bin", "cuda_nvrtc/bin",
                "cuda_runtime/bin", "cufft/bin", "nvjitlink/bin"):
        p = os.path.join(nv, *sub.split("/"))
        if os.path.isdir(p):
            try:
                os.add_dll_directory(p)
            except Exception:
                pass
            os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
            added.append(p)
    return added


_CUDA_DIRS = _setup_cuda_dlls()


def _free_vram():
    """把 Paddle 占着的显存还给系统。厚书连续跑会把 12G 吃满，不还就 OOM。"""
    try:
        import gc
        gc.collect()
        import paddle
        paddle.device.cuda.empty_cache()
    except Exception:
        pass

ROOT = r"E:\wengao"
MD_DIR = r"E:\wengao_md"
OCR_DIR = r"E:\wengao_ocr"
DB = r"E:\desktop\media\workbench.db"

HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")
HEAD2 = re.compile(r"^(第[一二三四五六七八九十百零〇\d]+[章节篇回卷部]|【.+?】|前言|序言?|目录|后记|附录)")

_ocr = None


def get_ocr():
    """用 PaddleOCR（GPU）：支持整本 PDF 一次性识别，实测约 1 秒/页，比 RapidOCR 逐页快 4-5 倍。"""
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="gpu",
        )
    return _ocr


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
    # 多进程同时写库（OCR/文本抽取/直播入库/转写）会撞锁，给足等待时间而不是立刻抛 database is locked
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=60000")
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
    return n


def ocr_book(pdf, name):
    """整本 PDF 交给 PaddleOCR 识别，返回 [(页码, 文本)]。

    PaddleOCR(GPU) 可以直接吃 PDF 路径，内部按页处理，实测约 1 秒/页（RapidOCR 逐页是 4.6 秒/页）。
    超过 200 页的厚书逐页送 numpy 数组，避免一次性把整本读进显存。
    """
    import numpy as np
    ocr = get_ocr()
    os.makedirs(OCR_DIR, exist_ok=True)
    d = fitz.open(pdf)
    n = d.page_count
    pages = []
    t0 = time.time()

    if n <= 200:
        try:
            res = ocr.predict(pdf)
            for k, item in enumerate(res):
                try:
                    txt = "\n".join(item.get("rec_texts") or []).strip()
                except Exception:
                    txt = ""
                if len(txt) >= 10:
                    pages.append((k + 1, txt))
            print("    整本 %d 页  均 %.2fs/页" % (n, (time.time() - t0) / max(n, 1)), flush=True)
            _free_vram()
            d.close()
            return pages, n
        except Exception as e:
            print("    整本识别失败（转逐页）: %s" % str(e)[:60], flush=True)
            _free_vram()

    for i in range(n):
        try:
            pix = d[i].get_pixmap(dpi=150)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                arr = arr[:, :, :3].copy()
            r = ocr.predict(arr)
            txt = ""
            if r:
                txt = "\n".join(r[0].get("rec_texts") or []).strip()
            del arr, pix
        except Exception:
            txt = ""
        if len(txt) >= 10:
            pages.append((i + 1, txt))
        # 每 20 页清一次显存：PaddleOCR 的显存池不会自己还，厚书会把 12G 吃满
        if (i + 1) % 20 == 0:
            _free_vram()
            print("    %d/%d 页  均 %.2fs/页" % (i + 1, n, (time.time() - t0) / (i + 1)), flush=True)
    _free_vram()
    d.close()
    return pages, n


def build_md(name, pages):
    out = ["# " + name, "", "> 来源：扫描版 PDF 本地 OCR（RapidOCR），可能有错字，原件保留。", ""]
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
    scope = sys.argv[1] if len(sys.argv) > 1 else "ALL"
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    c = sqlite3.connect(DB)
    done = {r[0] for r in c.execute("select title from books where ocr_state='done'")}
    c.close()

    cands = []
    for dp, _, fs in os.walk(ROOT):
        if "_已解压" in dp or "_原格式" in dp:
            continue
        for f in fs:
            if not f.lower().endswith(".pdf"):
                continue
            p = os.path.join(dp, f)
            if scope != "ALL" and scope not in p:
                continue
            if os.path.splitext(f)[0] in done:
                continue
            try:
                d = fitz.open(p)
                n = d.page_count
                ch = sum(len(d[i].get_text("text").strip()) for i in [0, n // 2] if n)
                d.close()
            except Exception:
                continue
            if ch >= 200:
                continue        # 有文字层，交给快路径
            cands.append((p, n))
    cands.sort(key=lambda x: x[1])      # 薄的先跑，出成果快
    if limit:
        cands = cands[:limit]
    total_pages = sum(n for _, n in cands)
    print("范围内扫描件 %d 本 / %d 页 / 预计 %.1f 小时" % (len(cands), total_pages, total_pages * 2.94 / 3600), flush=True)

    ok = fail = 0
    t0 = time.time()
    for i, (p, n) in enumerate(cands, 1):
        name = os.path.splitext(os.path.basename(p))[0]
        print("[%d/%d] %s (%d页)" % (i, len(cands), name[:44], n), flush=True)
        try:
            pages, n2 = ocr_book(p, name)
            if not pages:
                print("    没识别出内容，跳过", flush=True)
                fail += 1
                continue
            md = build_md(name, pages)
            os.makedirs(MD_DIR, exist_ok=True)
            open(os.path.join(MD_DIR, name + ".md"), "w", encoding="utf-8").write(md)
            nchunk = ingest(name, chunk_pages(pages), n2)
            ok += 1
            print("    OK %d 块  %d 字  累计 %.1f 小时"
                  % (nchunk, sum(len(t) for _, t in pages), (time.time() - t0) / 3600), flush=True)
        except Exception as e:
            fail += 1
            print("    失败 %s" % str(e)[:100], flush=True)

    print("\n完成：入库 %d 本，失败 %d 本，用时 %.1f 小时" % (ok, fail, (time.time() - t0) / 3600), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
