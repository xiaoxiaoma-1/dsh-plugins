# -*- coding: utf-8 -*-
"""按词测量：句末「了」vs「呢」的基频差，判断问句是否真的上扬"""
import os, sys, glob, sysconfig, subprocess
import numpy as np
import soundfile as sf

if hasattr(os, "add_dll_directory"):
    _sp = sysconfig.get_paths()["purelib"]
    for _d in glob.glob(os.path.join(_sp, "nvidia", "*", "bin")):
        try:
            os.add_dll_directory(_d)
        except OSError:
            pass
    _dirs = glob.glob(os.path.join(_sp, "nvidia", "*", "bin"))
    if _dirs:
        os.environ["PATH"] = os.pathsep.join(_dirs) + os.pathsep + os.environ.get("PATH", "")

from faster_whisper import WhisperModel

FF = r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
SR = 24000
KEY = '做不下去'

model = WhisperModel(r'E:\tools\asr\models\turbo', device='cuda', compute_type='float16')


def rd(p):
    d, sr = sf.read(p, dtype='float32')
    if d.ndim > 1:
        d = d.mean(axis=1)
    if sr != SR:
        d = np.interp(np.linspace(0, 1, int(len(d) * SR / sr)), np.linspace(0, 1, len(d))).astype('float32')
    return d


def f0_of(x, fmin=80, fmax=450, frame=0.03, hop=0.005):
    fl, hpl = int(frame * SR), int(hop * SR)
    out = []
    for s in range(0, max(0, len(x) - fl), hpl):
        fr = x[s:s + fl]
        if np.sqrt(np.mean(fr ** 2)) < 0.006:
            continue
        fr = fr - fr.mean()
        ac = np.correlate(fr, fr, 'full')[fl - 1:]
        lo, hi = int(SR / fmax), min(int(SR / fmin), len(ac) - 1)
        seg = ac[lo:hi]
        if len(seg):
            out.append(SR / (int(np.argmax(seg)) + lo))
    return np.array(out)


def m(a):
    return float(np.median(a)) if len(a) else 0.0


for v in (13, 14, 15):
    wav = rf'E:\tools\soulx-podcast\outputs\probe{v}.wav'
    if not os.path.exists(wav):
        continue
    t16 = rf'E:\desktop\media\_w{v}.wav'
    subprocess.run([FF, '-y', '-v', 'error', '-i', wav, '-ac', '1', '-ar', '16000',
                    '-c:a', 'pcm_s16le', t16], capture_output=True)
    a16, _ = sf.read(t16, dtype='float32')
    if a16.ndim > 1:
        a16 = a16.mean(axis=1)
    segs, _ = model.transcribe(a16.astype(np.float32), language='zh', beam_size=5,
                               word_timestamps=True, vad_filter=False)
    words = []
    for sg in segs:
        if KEY in sg.text or '不下去' in sg.text:
            words = [(w.start, w.end, w.word) for w in (sg.words or [])]
            break
    if not words:
        print(f'第{v}版: 没拿到词时间'); continue
    d = rd(wav)
    def segf0(w0, w1):
        return f0_of(d[max(0, int(w0 * SR)):min(len(d), int(w1 * SR))])
    zong = {w: (s, e) for s, e, w in words}
    print(f'\n===== 第{v}版 =====')
    print('  词表: ' + ' | '.join(f'{w}({s:.2f}-{e:.2f})' for s, e, w in words))
    # 「了」和「呢」
    le = next(((s, e) for s, e, w in words if '了' in w), None)
    ne = next(((s, e) for s, e, w in words if '呢' in w), None)
    zuo = next(((s, e) for s, e, w in words if '怎么' in w or w == '怎么'), None)
    if le and ne:
        f_le, f_ne = m(segf0(*le)), m(segf0(*ne))
        print(f'  「了」{f_le:6.1f}Hz → 「呢」{f_ne:6.1f}Hz   差 {f_ne - f_le:+.1f}Hz  '
              f'{"上扬 ↑↑" if f_ne - f_le > 15 else ("略扬 ↑" if f_ne - f_le > 5 else ("持平 →" if f_ne - f_le > -5 else "下沉 ↓"))}')
    if zuo and ne:
        f_z, f_n = m(segf0(*zuo)), m(segf0(*ne))
        print(f'  「怎么」{f_z:6.1f}Hz → 「呢」{f_n:6.1f}Hz   差 {f_n - f_z:+.1f}Hz')
