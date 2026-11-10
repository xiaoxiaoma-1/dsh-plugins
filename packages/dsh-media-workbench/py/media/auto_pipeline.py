# -*- coding: utf-8 -*-
"""批量转写 + 简写 + 分类 + 入库（直播/抖音新录内容的全自动管线第一版）

步骤：wav 无 txt → whisper 转写 → condense 去口水 → 分类 → 入库 posts/live_segments
用法：python auto_pipeline.py [--transcribe-only]
"""
import glob
import json
import os
import re
import sqlite3
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
ASR_DIR = r"E:\tools\asr"
OUT_DIR = r"E:\tools\asr\out"
PY = os.path.join(ASR_DIR, ".venv", "Scripts", "python.exe")
DB = r"E:\desktop\media\workbench.db"
LOG = r"E:\desktop\media\_auto_pipeline.log"


def log(msg):
    line = "%s  %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def pending_wavs():
    wavs = {os.path.splitext(os.path.basename(f))[0]: f for f in glob.glob(os.path.join(OUT_DIR, "*.wav"))}
    txts = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(OUT_DIR, "*.txt"))}
    return [(k, wavs[k]) for k in sorted(set(wavs) - txts)]


def transcribe(wav):
    env = dict(os.environ, ASR_DEVICE="cpu")   # 用户在电脑上时不抢 GPU
    t0 = time.time()
    r = subprocess.run([PY, os.path.join(ASR_DIR, "transcribe.py"), wav],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore", env=env, cwd=ASR_DIR)
    ok = r.returncode == 0
    log("   转写 %s %s（%.0f 秒）" % (os.path.basename(wav), "成功" if ok else "失败", time.time() - t0))
    if not ok and r.stderr:
        log("   stderr: " + r.stderr.strip().splitlines()[-1][:160])
    return ok


def main():
    only_tr = "--transcribe-only" in sys.argv
    todo = pending_wavs()
    log("=== 待转写 %d 个 ===" % len(todo))
    done = 0
    for name, wav in todo:
        if transcribe(wav):
            done += 1
    log("=== 转写完成 %d / %d ===" % (done, len(todo)))
    if only_tr:
        return
    # 后续：去口水 + 分类 + 入库（下一版接上）
    log("（去口水/分类/入库待接）")


if __name__ == "__main__":
    main()
