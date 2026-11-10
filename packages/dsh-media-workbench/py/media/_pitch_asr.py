# -*- coding: utf-8 -*-
"""用 ASR 精确定位「做不下去」那句，再对比第13/14版的语调走势"""
import os, sys, glob, sysconfig, subprocess
import numpy as np

# ctranslate2 找 cuda dll
if hasattr(os, "add_dll_directory"):
    _sp = sysconfig.get_paths()["purelib"]
    _dirs = glob.glob(os.path.join(_sp, "nvidia", "*", "bin"))
    for _d in _dirs:
        try:
            os.add_dll_directory(_d)
        except OSError:
            pass
    if _dirs:
        os.environ["PATH"] = os.pathsep.join(_dirs) + os.pathsep + os.environ.get("PATH", "")

import soundfile as sf
from faster_whisper import WhisperModel

FF = r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
SR = 24000
KEY = '做不下去'


def to16k(src, dst):
    subprocess.run([FF, '-y', '-v', 'error', '-i', src, '-ac', '1', '-ar', '16000',
                    '-c:a', 'pcm_s16le', dst], capture_output=True)


def load24(p):
    d, sr = sf.read(p, dtype='float32')
    if d.ndim > 1:
        d = d.mean(axis=1)
    if sr != SR:
        d = np.interp(np.linspace(0, 1, int(len(d) * SR / sr)), np.linspace(0, 1, len(d))).astype('float32')
    return d


def f0_curve(x, fmin=70, fmax=400, frame=0.04, hop=0.01):
    fl, hpl = int(frame * SR), int(hop * SR)
    f0 = []
    for s in range(0, max(0, len(x) - fl), hpl):
        fr = x[s:s + fl]
        if np.sqrt(np.mean(fr ** 2)) < 0.008:
            f0.append(0.0); continue
        fr = fr - fr.mean()
        ac = np.correlate(fr, fr, 'full')[fl - 1:]
        lo, hi = int(SR / fmax), min(int(SR / fmin), len(ac) - 1)
        seg = ac[lo:hi]
        f0.append(SR / (int(np.argmax(seg)) + lo) if len(seg) else 0.0)
    return np.array(f0)


def med(a):
    a = a[a > 0]
    return float(np.median(a)) if len(a) else 0.0


model = WhisperModel(r'E:\tools\asr\models\turbo', device='cuda', compute_type='float16')

for v in (13, 14, 15):
    wav = rf'E:\tools\soulx-podcast\outputs\probe{v}.wav'
    if not os.path.exists(wav):
        print(f'第{v}版: 文件不存在'); continue
    tmp = rf'E:\desktop\media\_asr{v}.wav'
    to16k(wav, tmp)
    aud16, sr16 = sf.read(tmp, dtype='float32')   # 直接喂数组，绕开 av 解码兼容问题
    if aud16.ndim > 1:
        aud16 = aud16.mean(axis=1)
    segs, _ = model.transcribe(aud16.astype(np.float32), language='zh', beam_size=5,
                               word_timestamps=True, vad_filter=False)
    hit = None
    allt = []
    for sg in segs:
        txt = sg.text.strip()
        allt.append((sg.start, sg.end, txt))
        if KEY in txt or '做不下去' in txt or '不下去' in txt:
            hit = (sg.start, sg.end, txt)
            break
    print(f'\n===== 第{v}版 =====')
    for st, en, tx in allt[:8]:
        print(f'  {st:5.2f}-{en:5.2f}  {tx}')
    if not hit:
        print('  没找到关键词，用前 8 段里的第 5 段兜底')
        if len(allt) >= 5:
            hit = allt[4]
        else:
            continue
    st, en, tx = hit
    print(f'\n>>> 定位: {st:.2f}-{en:.2f}s  「{tx}」')
    d = load24(wav)
    pad = 0.08
    a = max(0, int((st - pad) * SR)); b = min(len(d), int((en + pad) * SR))
    x = d[a:b]
    f0 = f0_curve(x)
    n = len(f0)
    p1, p2, p3 = med(f0[:n // 3]), med(f0[n // 3:2 * n // 3]), med(f0[2 * n // 3:])
    tail = med(f0[-int(0.30 / 0.01):])
    mid = med(f0[int(n * 0.35):int(n * 0.65)])
    head = med(f0[:int(0.30 / 0.01)])
    print(f'  F0: 开头 {head:5.1f} | 前段 {p1:5.1f} | 中段 {p2:5.1f} | 后段 {p3:5.1f} | 尾音 {tail:5.1f} Hz')
    print(f'  尾部 vs 句中: {tail - mid:+.1f}Hz  → {"上扬 ↑" if tail - mid > 8 else ("下沉 ↓" if tail - mid < -8 else "基本平 →")}')
    print(f'  整体 开头→结尾: {tail - head:+.1f}Hz')
