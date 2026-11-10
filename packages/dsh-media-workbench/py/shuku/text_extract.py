# -*- coding: utf-8 -*-
"""文字版 PDF 直提：不经过 OCR，直接把全文抽出来 → 切块入库 → 标记 done。

OCR 队列只处理扫描件（前两页文字 < 200 字），文字版书籍以前会被跳过、永远不入库。
这个脚本补上那一段：每 10 分钟扫一遍 E:\\wengao，把文字版还没入库的书直接提出来。

用法：python text_extract.py [--once]
"""
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fitz  # noqa: E402
import ocr_pipeline as op  # noqa: E402

LOG = os.path.join(HERE, "text_extract.log")
STOP = os.path.join(HERE, "STOP_TEXT_EXTRACT")


def log(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def done_titles(db):
    import sqlite3
    c = sqlite3.connect(db, timeout=60)
    try:
        c.execute("PRAGMA busy_timeout=60000")
        return {r[0] for r in c.execute("select title from books where ocr_state='done'")}
    finally:
        c.close()


def run_once():
    import sqlite3
    done = done_titles(op.DB)
    todo = []
    for dp, _, fs in os.walk(op.ROOT):
        if "_已解压" in dp or "_原格式" in dp:
            continue
        for f in fs:
            if not f.lower().endswith(".pdf"):
                continue
            stem = os.path.splitext(f)[0]
            if stem in done:
                continue
            p = os.path.join(dp, f)
            try:
                d = fitz.open(p)
                n = d.page_count
                # 取前 3 页判断是不是文字版：扫描件的封面/扉页几乎没有可提取文字
                head = sum(len((d[i].get_text("text") or "").strip()) for i in range(min(3, n)))
                d.close()
            except Exception:
                continue
            if head >= 300:        # 文字版
                todo.append((n, p, stem))

    if not todo:
        return 0
    todo.sort()
    ok = 0
    for n, p, name in todo:
        try:
            d = fitz.open(p)
            pages = [(i + 1, d[i].get_text("text")) for i in range(n)]
            d.close()
            md = op.build_md(name, pages)
            md = md.replace("扫描版 PDF 本地 OCR（RapidOCR），可能有错字，原件保留。",
                            "文字版 PDF 直接提取，未经过 OCR。")
            os.makedirs(op.MD_DIR, exist_ok=True)
            with open(os.path.join(op.MD_DIR, name + ".md"), "w", encoding="utf-8") as f:
                f.write(md)
            nchunk = None
            for attempt in range(5):
                try:
                    nchunk = op.ingest(name, op.chunk_pages(pages), n)
                    break
                except Exception as e:
                    if 'locked' in str(e) and attempt < 4:
                        log("入库被锁，5 秒后重试 %s（第 %d 次）" % (name[:30], attempt + 1))
                        time.sleep(5)
                        continue
                    raise
            log("直提完成 %s：%d 页 %d 块" % (name[:40], n, nchunk or 0))
            ok += 1
        except Exception as e:
            log("直提失败 %s：%s" % (name[:40], str(e)[:150]))
            traceback.print_exc()
    return ok


def main():
    once = "--once" in sys.argv
    log("=== 文字版直提启动 ===")
    while True:
        if os.path.exists(STOP):
            log("发现 STOP_TEXT_EXTRACT，退出")
            os.remove(STOP)
            return
        try:
            n = run_once()
            if n:
                log("本轮直提 %d 本" % n)
        except Exception as e:
            log("循环异常：%s" % str(e)[:200])
        if once:
            break
        time.sleep(600)


if __name__ == "__main__":
    main()
