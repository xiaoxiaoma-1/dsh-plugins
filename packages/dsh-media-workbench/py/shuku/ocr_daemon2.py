# -*- coding: utf-8 -*-
"""OCR 长驻队列：一本一本跑剩余扫描件，断点续跑，可以挂几天。

- 每本跑完立刻入库，崩了重启也不重复
- 每本之间歇 3 秒，避免一直占满
- 停止：在 E:\\desktop\\书库盘点\\ 下建一个 STOP_OCR 文件，跑完当前这本就退出
- 日志：E:\\desktop\\书库盘点\\ocr_daemon.log
"""
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

STOP = os.path.join(HERE, "STOP_OCR")
LOG = os.path.join(HERE, "ocr_daemon.log")


def log(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    import fitz
    import ocr_pipeline as op

    ROOT = op.ROOT
    DB = op.DB
    log("=== daemon2 启动（厚书优先） ===")
    while True:
        if os.path.exists(STOP):
            log("发现 STOP_OCR，退出")
            os.remove(STOP)
            return
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
                    continue
                cands.append((n, p))
        if not cands:
            log("没有待 OCR 的扫描件了，退出")
            return

        cands.sort(reverse=True)     # 从厚书开始跑，和主进程错开
        n, p = cands[0]
        name = os.path.splitext(os.path.basename(p))[0]
        log("开始 %s（%d 页，队列还剩 %d 本）" % (name[:40], n, len(cands)))
        try:
            pages, n2 = op.ocr_book(p, name)
            if pages:
                md = op.build_md(name, pages)
                os.makedirs(op.MD_DIR, exist_ok=True)
                open(os.path.join(op.MD_DIR, name + ".md"), "w", encoding="utf-8").write(md)
                nchunk = op.ingest(name, op.chunk_pages(pages), n2)
                log("完成 %s：%d 块" % (name[:40], nchunk))
            else:
                log("跳过 %s：没识别出内容" % name[:40])
                # 标记成 done 免得反复重试
                c = sqlite3.connect(DB)
                try:
                    c.execute("insert into books(id,title,ocr_state,created_at) values(?,?,?,datetime('now'))",
                              ("skip_" + os.urandom(4).hex(), name, "done"))
                    c.commit()
                finally:
                    c.close()
        except Exception as e:
            log("失败 %s：%s" % (name[:40], str(e)[:120]))
        time.sleep(3)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
