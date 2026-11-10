# -*- coding: utf-8 -*-
"""对比第13版/第14版里「怎么就做不下去了呢」这句的语调走势（前中后三段基频 + 末段是否上扬）"""
import sys, numpy as np, soundfile as sf

SR = 24000
FF_TARGET = [13, 14]


def load(p):
    d, sr = sf.read(p, dtype='float32')
    if d.ndim > 1:
        d = d.mean(axis=1)
    if sr != SR:
        d = np.interp(np.linspace(0, 1, int(len(d) * SR / sr)), np.linspace(0, 1, len(d))).astype('float32')
    return d


def segments(d, th=0.012, min_sil=0.12, min_seg=0.12):
    """按静音切段，返回 [(start,end)]"""
    quiet = np.abs(d) < th
    segs, i, n = [], 0, len(d)
    in_speech = False
    start = 0
    while i < n:
        if not quiet[i] and not in_speech:
            in_speech = True
            start = i
        elif quiet[i] and in_speech:
            j = i
            while j < n and quiet[j]:
                j += 1
            if (j - i) > int(min_sil * SR):
                if (i - start) > int(min_seg * SR):
                    segs.append((start, i))
                in_speech = False
            i = j
            continue
        i += 1
    if in_speech and (n - start) > int(min_seg * SR):
        segs.append((start, n))
    return segs


def f0_curve(x, fmin=70, fmax=400, frame=0.04, hop=0.01):
    """自相关基频，返回 (times, f0)，无声帧 f0=0"""
    fl, hpl = int(frame * SR), int(hop * SR)
    f0s, times = [], []
    for s in range(0, max(0, len(x) - fl), hpl):
        fr = x[s:s + fl]
        if np.sqrt(np.mean(fr ** 2)) < 0.008:
            f0s.append(0.0); times.append(s / SR); continue
        fr = fr - fr.mean()
        ac = np.correlate(fr, fr, 'full')[fl - 1:]
        lo, hi = int(SR / fmax), int(SR / fmin)
        if hi >= len(ac):
            hi = len(ac) - 1
        seg = ac[lo:hi]
        if len(seg) == 0:
            f0s.append(0.0); times.append(s / SR); continue
        pk = int(np.argmax(seg)) + lo
        f0s.append(SR / pk if pk > 0 else 0.0)
        times.append(s / SR)
    return np.array(times), np.array(f0s)


def analyze(path, label):
    d = load(path)
    segs = segments(d)
    print(f'\n===== {label} =====')
    print(f'总时长 {len(d)/SR:.1f}s，切出 {len(segs)} 段')
    for k, (s, e) in enumerate(segs[:9]):
        print(f'  段{k+1}: {s/SR:5.2f}-{e/SR:5.2f}s  {((e-s)/SR):.2f}s')
    if len(segs) < 5:
        print('段数不足，无法定位第5轮')
        return
    s, e = segs[4]
    x = d[s:e]
    dur = (e - s) / SR
    print(f'\n---> 取第5段（{s/SR:.2f}-{e/SR:.2f}s，{dur:.2f}s）当作「我就纳闷啊…做不下去了呢」')
    t, f0 = f0_curve(x)
    v = f0[f0 > 0]
    if len(v) < 10:
        print('有效基频帧太少')
        return
    third = len(f0) // 3
    def med(a):
        a = a[a > 0]
        return float(np.median(a)) if len(a) else 0.0
    p1, p2, p3 = med(f0[:third]), med(f0[third:2 * third]), med(f0[2 * third:])
    # 最后 0.35 秒 vs 之前的中段（问句尾音）
    tail_n = int(0.35 / 0.01)
    tail = med(f0[-tail_n:])
    mid = med(f0[int(len(f0)*0.4):int(len(f0)*0.7)])
    print(f'F0 中位数：前段 {p1:6.1f}Hz | 中段 {p2:6.1f}Hz | 后段 {p3:6.1f}Hz')
    print(f'尾音(末0.35s) {tail:6.1f}Hz vs 句中 {mid:6.1f}Hz  → 差值 {tail-mid:+.1f}Hz  '
          f'{"上扬 ↑" if tail - mid > 8 else ("下沉 ↓" if tail - mid < -8 else "基本平 →")}')
    print(f'整段基频范围 {v.min():.0f}-{v.max():.0f}Hz，标准差 {v.std():.0f}')


for v in FF_TARGET:
    p = rf'E:\tools\soulx-podcast\outputs\probe{v}.wav'
    try:
        analyze(p, f'第{v}版')
    except Exception as ex:
        print(f'第{v}版分析失败: {ex}')
