# -*- coding: utf-8 -*-
"""用 YIN 重测句末「了」与「呢」的基频（自相关法八度错误太多，改用 YIN 首个谷判定）"""
import os, glob, sysconfig, subprocess
import numpy as np
import soundfile as sf

SR = 24000
FF = r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'


def rd(p):
    d, sr = sf.read(p, dtype='float32')
    if d.ndim > 1:
        d = d.mean(axis=1)
    if sr != SR:
        d = np.interp(np.linspace(0, 1, int(len(d) * SR / sr)), np.linspace(0, 1, len(d))).astype('float32')
    return d


def yin_frame(fr, sr, fmin=80, fmax=450, th=0.12):
    """YIN：取 CMND 第一个低于阈值的谷，抗八度误判"""
    N = len(fr)
    W = int(sr / fmin)
    if N < 2 * W:
        return 0.0
    lim = N - W
    d = np.zeros(W)
    for tau in range(1, W):
        diff = fr[:lim] - fr[tau:tau + lim]
        d[tau] = float(np.dot(diff, diff))
    cmnd = np.ones(W)
    run = 0.0
    for tau in range(1, W):
        run += d[tau]
        cmnd[tau] = d[tau] * tau / run if run > 1e-12 else 1.0
    lo, hi = int(sr / fmax), W
    best = 0.0
    for tau in range(lo, hi):
        if cmnd[tau] < th:
            while tau + 1 < hi and cmnd[tau + 1] < cmnd[tau]:
                tau += 1
            best = sr / tau
            break
    return best


def f0_series(x, sr=SR, frame=0.045, hop=0.008):
    fl, hpl = int(frame * sr), int(hop * sr)
    out = []
    for s in range(0, max(0, len(x) - fl), hpl):
        fr = x[s:s + fl]
        if np.sqrt(np.mean(fr ** 2)) < 0.006:
            continue
        v = yin_frame(fr - fr.mean(), sr)
        if 70 < v < 500:
            out.append(v)
    return np.array(out)


def med(a):
    return float(np.median(a)) if len(a) else 0.0


def pct(a, p):
    return float(np.percentile(a, p)) if len(a) else 0.0


# 各版词边界（来自上一轮 ASR 词时间戳）
DATA = {
    13: {'怎么': (8.00, 8.60), '下去': (9.06, 9.36), '呢': (9.36, 9.62)},
    14: {'怎么': (10.00, 10.40), '了': (11.22, 11.56), '呢': (11.56, 11.76)},
    15: {'怎么': (9.98, 10.38), '了': (11.12, 11.48), '呢': (11.48, 11.68)},
}

for v, parts in DATA.items():
    wav = rf'E:\tools\soulx-podcast\outputs\probe{v}.wav'
    if not os.path.exists(wav):
        continue
    d = rd(wav)
    print(f'\n===== 第{v}版（YIN）=====')
    vals = {}
    for name, (s, e) in parts.items():
        x = d[max(0, int(s * SR)):min(len(d), int(e * SR))]
        f = f0_series(x)
        vals[name] = med(f)
        print(f'  {name:4s} {s:.2f}-{e:.2f}s  中位 {med(f):6.1f}Hz  10% {pct(f,10):6.1f}  90% {pct(f,90):6.1f}  (帧 {len(f)})')
    if '了' in vals and '呢' in vals:
        diff = vals['呢'] - vals['了']
        tag = '上扬 ↑↑' if diff > 15 else ('略扬 ↑' if diff > 5 else ('持平 →' if diff > -5 else '下沉 ↓'))
        print(f'  ==> 「了」→「呢」 {diff:+.1f}Hz  {tag}')
    if '怎么' in vals and '呢' in vals:
        print(f'  ==> 「怎么」→「呢」 {vals["呢"]-vals["怎么"]:+.1f}Hz')
