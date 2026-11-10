# -*- coding: utf-8 -*-
"""书库 OCR 状态 / 扫描新书（给工作台稿库面板用）。

用法：
  python ocr_status.py            # 快速状态：书总数、已转、OCR 队列、正在 OCR 哪本
  python ocr_status.py --scan     # 扫描 E:\\wengao 里还没入库的新 PDF，并区分「文字版/扫描件」
"""
import json
import os
import re
import sqlite3
import sys
import time

ROOT = r'E:\wengao'
DB = r'E:\desktop\media\workbench.db'
LOG = r'E:\desktop\书库盘点\ocr_daemon.log'
OUT_LOG = r'E:\tools\DouyinLiveRecorder\logs\ocr_out.log'


def last_progress():
    """从 stdout 日志里取「20/119 页」这种进度。"""
    try:
        with open(OUT_LOG, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-80:]
    except OSError:
        return None
    for ln in reversed(lines):
        m = re.search(r'(\d+)/(\d+) 页', ln)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def log_tail(n=400):
    try:
        with open(LOG, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-n:]
        return lines
    except OSError:
        return []


def parse_log(lines):
    cur = None
    left = None
    batch_done = 0
    last_kind = None
    done_ts = []
    for ln in lines:
        mt = re.match(r'\[(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\]', ln)
        ts = None
        if mt:
            ts = (int(mt.group(2)), int(mt.group(3)), int(mt.group(4)), int(mt.group(5)))
        m = re.search(r'开始 (.+?)（(\d+) 页，队列还剩 (\d+) 本）', ln)
        if m:
            cur = {'title': m.group(1), 'pages': int(m.group(2))}
            left = int(m.group(3))
            last_kind = 'start'
        if '完成 ' in ln and '：' in ln:
            batch_done += 1
            last_kind = 'done'
            if ts:
                done_ts.append(ts)
    # 最后一行是"完成"→ 上一本刚结束，正在切下一本，此刻没有"正在处理的书"
    if last_kind == 'done':
        cur = None
    return cur, left, batch_done, done_ts


def avg_minutes_per_book(done_ts, n=10):
    """用最近 n 次"完成"的间隔估平均每本耗时（分钟）。"""
    pts = done_ts[-n - 1:]
    if len(pts) < 3:
        return None
    gaps = []
    for a, b in zip(pts, pts[1:]):
        sec = (b[0] * 86400 + b[1] * 3600 + b[2] * 60 + b[3]) - \
              (a[0] * 86400 + a[1] * 3600 + a[2] * 60 + a[3])
        if 0 < sec < 3600:
            gaps.append(sec / 60.0)
    return round(sum(gaps) / len(gaps), 2) if gaps else None


def scan_new():
    conn = sqlite3.connect(DB)
    known = {r[0] for r in conn.execute('select title from books')}
    conn.close()

    new = []
    for dp, _, fs in os.walk(ROOT):
        if '_已解压' in dp or '_原格式' in dp:
            continue
        for f in fs:
            if not f.lower().endswith('.pdf'):
                continue
            stem = os.path.splitext(f)[0]
            if stem in known:
                continue
            new.append(os.path.join(dp, f))

    text_like = []
    scanned = []
    import fitz
    for p in new:
        try:
            d = fitz.open(p)
            n = d.page_count
            txt = ''
            for i in range(min(3, n)):
                txt += d[i].get_text('text') or ''
            d.close()
        except Exception:
            scanned.append(p)
            continue
        if len(txt.strip()) >= 300:
            text_like.append(p)
        else:
            scanned.append(p)
    return {
        'ok': True,
        'newCount': len(new),
        'textCount': len(text_like),
        'scanCount': len(scanned),
        'names': [os.path.basename(p) for p in new[:10]],
    }


def status():
    conn = sqlite3.connect(DB)
    total = conn.execute('select count(*) from books').fetchone()[0]
    done = conn.execute("select count(*) from books where ocr_state='done'").fetchone()[0]
    conn.close()

    pdfs = 0
    for dp, _, fs in os.walk(ROOT):
        if '_已解压' in dp or '_原格式' in dp:
            continue
        pdfs += sum(1 for f in fs if f.lower().endswith('.pdf'))

    cur, left, batch_done, done_ts = parse_log(log_tail())
    running = False
    try:
        running = time.time() - os.path.getmtime(LOG) < 900   # 15 分钟内有动静才算在跑
    except OSError:
        pass
    pg = last_progress()
    if cur and pg:
        cur['donePages'], cur['totalPages'] = pg
    # 待 OCR 用日志里的队列剩余（OCR 程序自己算的，准）；
    # 不能拿 pdfs - done，因为 done 里混着 EPUB 和文字版 PDF，两个数不同源。
    pending = left if left is not None else max(0, pdfs - done)
    per = avg_minutes_per_book(done_ts)
    eta = None
    if running and per and left:
        mins = int(round(left * per))
        eta = {'minutes': mins, 'finishAt': time.strftime(
            '%m-%d %H:%M', time.localtime(time.time() + mins * 60))}
    return {
        'ok': True,
        'books': total,
        'done': done,
        'pdfs': pdfs,
        'pending': pending,
        'queueLeft': pending,
        'current': cur if running else None,
        'batchDone': batch_done,
        'avgMinutesPerBook': per,
        'eta': eta,
        'running': running,
        'root': ROOT,
    }


if __name__ == '__main__':
    if '--scan' in sys.argv:
        out = scan_new()
    elif '--watch' in sys.argv:
        try:
            while True:
                s = status()
                cur = s['current']
                line = '剩 %s 本' % s['queueLeft']
                if cur:
                    pgd = cur.get('donePages')
                    pgt = cur.get('totalPages')
                    line += ' | 正在：%s' % cur['title'][:26]
                    if pgd is not None:
                        line += ' %s/%s 页' % (pgd, pgt)
                if s['eta']:
                    line += ' | 约 %d 分钟后完成（%s）' % (s['eta']['minutes'], s['eta']['finishAt'])
                print(time.strftime('[%H:%M:%S] ') + line, flush=True)
                time.sleep(10)
        except KeyboardInterrupt:
            pass
        sys.exit(0)
    else:
        out = status()
    print(json.dumps(out, ensure_ascii=False))

