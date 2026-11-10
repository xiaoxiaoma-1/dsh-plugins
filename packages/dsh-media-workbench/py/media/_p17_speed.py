# -*- coding: utf-8 -*-
"""第15版：对「怎么就做不下去了呢？」做韵律后处理——前快后慢 + 末尾语气上扬（rubberband）"""
import os, sys, glob, sysconfig, subprocess
import numpy as np
import soundfile as sf

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

from faster_whisper import WhisperModel

FF = r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
SRC = r'E:\tools\soulx-podcast\outputs\probe14.wav'
DST = r'E:\tools\soulx-podcast\outputs\probe17.wav'
MP3 = r'E:\desktop\播客样音_SoulX第17版_只变速不变调.mp3'
TMP = r'E:\desktop\media\_p15'
SR = 24000
KEY = '做不下去'

os.makedirs(TMP, exist_ok=True)


def rd(p):
    d, sr = sf.read(p, dtype='float32')
    if d.ndim > 1:
        d = d.mean(axis=1)
    if sr != SR:
        d = np.interp(np.linspace(0, 1, int(len(d) * SR / sr)), np.linspace(0, 1, len(d))).astype('float32')
    return d


def wr(p, d):
    sf.write(p, d.astype('float32'), SR)


def rubber(src_wav, dst_wav, tempo, pitch):
    af = f'rubberband=tempo={tempo}:pitch={pitch}:transients=smooth:formant=preserved'
    r = subprocess.run([FF, '-y', '-v', 'error', '-i', src_wav, '-af', af,
                        '-ar', str(SR), '-ac', '1', dst_wav], capture_output=True, text=True)
    if r.returncode != 0:
        print('[rubberband 失败]', r.stderr[-300:])
    return r.returncode == 0


# 1) 定位这句
sixteen = os.path.join(TMP, 'src16.wav')
subprocess.run([FF, '-y', '-v', 'error', '-i', SRC, '-ac', '1', '-ar', '16000',
                '-c:a', 'pcm_s16le', sixteen], capture_output=True)
aud16, _ = sf.read(sixteen, dtype='float32')
if aud16.ndim > 1:
    aud16 = aud16.mean(axis=1)
model = WhisperModel(r'E:\tools\asr\models\turbo', device='cuda', compute_type='float16')
segs, _ = model.transcribe(aud16.astype(np.float32), language='zh', beam_size=5,
                           word_timestamps=True, vad_filter=False)
s0 = e0 = None
words = []
for sg in segs:
    if KEY in sg.text or '不下去' in sg.text:
        s0, e0 = sg.start, sg.end
        for w in (sg.words or []):
            words.append((w.start, w.end, w.word))
        break
if s0 is None:
    print('定位失败'); sys.exit(1)
print(f'定位: {s0:.2f}-{e0:.2f}s')
for st, en, wd in words:
    print(f'   {st:5.2f}-{en:5.2f}  {wd}')

d = rd(SRC)
a = max(0, int((s0 - 0.02) * SR))
b = min(len(d), int((e0 + 0.06) * SR))
seg = d[a:b]
n = len(seg)
print(f'切出 {n/SR:.2f}s')

# 2) 三段：前快 / 中平 / 尾上扬
cuts = [0.0, 0.42, 0.72, 1.0]
plans = [  # (tempo, pitch)
    (1.07, 1.000),   # 怎么就 / 做不下 —— 只快，绝不碰音高
    (1.00, 1.000),   # 去了 —— 常速
    (0.93, 1.000),   # 呢？—— 放慢拖长，音高不碰
]
parts = []
for i in range(3):
    i0 = int(cuts[i] * n)
    i1 = int(cuts[i + 1] * n)
    if i1 - i0 < int(0.05 * SR):
        continue
    raw = os.path.join(TMP, f'raw{i}.wav')
    out = os.path.join(TMP, f'out{i}.wav')
    wr(raw, seg[i0:i1])
    tempo, pitch = plans[i]
    if rubber(raw, out, tempo, pitch):
        parts.append(rd(out))
        print(f'  段{i+1}: {i0/SR:.2f}-{i1/SR:.2f}s → tempo {tempo} pitch {pitch} 输出 {len(parts[-1])/SR:.2f}s')
    else:
        parts.append(seg[i0:i1])

# 3) 拼接（25ms 交叉淡化）
XF = int(0.025 * SR)
merged = parts[0]
for p in parts[1:]:
    xf = min(XF, len(merged) // 4, len(p) // 4)
    if xf > 0:
        f = np.linspace(0, 1, xf, dtype='float32')
        head = merged[-xf:] * (1 - f) + p[:xf] * f
        merged = np.concatenate([merged[:-xf], head, p[xf:]])
    else:
        merged = np.concatenate([merged, p])
print(f'处理后该句 {len(merged)/SR:.2f}s（原 {len(seg)/SR:.2f}s）')

new = np.concatenate([d[:a], merged, d[b:]])
peak = float(np.max(np.abs(new))) or 1.0
if peak > 0.98:
    new = new / peak * 0.95
wr(DST, new)

subprocess.run([FF, '-y', '-v', 'error', '-i', DST, '-c:a', 'libmp3lame', '-b:a', '128k', MP3],
               capture_output=True)
print(f'已导出: {MP3}  ({len(new)/SR:.1f}s)')
