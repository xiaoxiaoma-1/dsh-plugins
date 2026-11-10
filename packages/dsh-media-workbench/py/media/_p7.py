# -*- coding: utf-8 -*-
"""只拉长停顿，不插任何外来音频（避免电音）"""
import os, subprocess, numpy as np, soundfile as sf

FF = r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
SRC = r'E:\tools\soulx-podcast\outputs\probe7.wav'
SR = 24000

d, sr = sf.read(SRC, dtype='float32')
if d.ndim > 1:
    d = d.mean(axis=1)
if sr != SR:
    d = np.interp(np.linspace(0, 1, int(len(d) * SR / sr)), np.linspace(0, 1, len(d))).astype('float32')

quiet = np.abs(d) < 0.012
runs, i = [], 0
while i < len(quiet):
    if quiet[i]:
        j = i
        while j < len(quiet) and quiet[j]:
            j += 1
        if (j - i) > int(0.14 * SR):
            runs.append((i, j))
        i = j
    else:
        i += 1

# 取最长的 5 处停顿，各加 0.22s
picks = sorted(runs, key=lambda r: -(r[1] - r[0]))[:5]
picks.sort()
out = d.copy()
shift = 0
for s, e in picks:
    pos = (s + e) // 2 + shift
    pad = int(0.22 * SR)
    out = np.concatenate([out[:pos], np.zeros(pad, dtype='float32'), out[pos:]])
    shift += pad

peak = float(np.max(np.abs(out))) or 1.0
out = out / peak * 0.92
tmp = r'E:\desktop\media\_p7.wav'
sf.write(tmp, out, SR)
dst = r'E:\desktop\播客样音_SoulX第七版.mp3'
subprocess.run([FF, '-y', '-i', tmp, '-c:a', 'libmp3lame', '-b:a', '128k', dst], capture_output=True)
os.remove(tmp)
print('silences', len(runs), 'padded', len(picks), 'dur', round(len(out) / SR, 1), '|',
      round(os.path.getsize(dst) / 1024), 'KB', flush=True)
