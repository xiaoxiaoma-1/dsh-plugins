# -*- coding: utf-8 -*-
"""把三段对谈拼成 10 分钟播客：修掉段首段尾多余静音，段间留 400ms 气口，导出 mp3"""
import os, subprocess
import numpy as np
import soundfile as sf

SR = 24000
FF = r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
BASE = r'E:\tools\soulx-podcast\outputs'
SEGS = ['probe19.wav', 'probe_p20a.wav', 'probe_p20b.wav']
OUT_WAV = os.path.join(BASE, 'podcast10.wav')
OUT_MP3 = r'E:\desktop\播客_十分钟完整版_具体化.mp3'

HEAD_KEEP = 0.06     # 段首保留
TAIL_KEEP = 0.34     # 段尾保留
GAP = 0.0            # 额外插入（0 = 靠 TAIL_KEEP+HEAD_KEEP 形成约 400ms 气口）
FADE = 0.008         # 段间淡化，防爆音


def rd(p):
    d, sr = sf.read(p, dtype='float32')
    if d.ndim > 1:
        d = d.mean(axis=1)
    if sr != SR:
        d = np.interp(np.linspace(0, 1, int(len(d) * SR / sr)), np.linspace(0, 1, len(d))).astype('float32')
    return d


def trim(d, th=0.008, head_keep=HEAD_KEEP, tail_keep=TAIL_KEEP):
    idx = np.where(np.abs(d) > th)[0]
    if len(idx) == 0:
        return d
    a = max(0, idx[0] - int(head_keep * SR))
    b = min(len(d), idx[-1] + int(tail_keep * SR))
    return d[a:b]


parts = []
for i, name in enumerate(SEGS):
    p = os.path.join(BASE, name)
    if not os.path.exists(p):
        print(f'[缺文件] {p}')
        continue
    d = rd(p)
    raw = len(d) / SR
    d = trim(d)
    print(f'{name}: {raw:.1f}s → 修剪后 {len(d)/SR:.1f}s')
    parts.append(d)

if not parts:
    raise SystemExit('没有可拼接的段')

# 段间：末尾淡出 + 间隙 + 开头淡入
merged = parts[0].copy()
fi = int(FADE * SR)
for d in parts[1:]:
    merged[-fi:] *= np.linspace(1, 0, fi, dtype='float32')
    if GAP > 0:
        merged = np.concatenate([merged, np.zeros(int(GAP * SR), dtype='float32')])
    head = d.copy()
    head[:fi] *= np.linspace(0, 1, fi, dtype='float32')
    merged = np.concatenate([merged, head])

peak = float(np.max(np.abs(merged))) or 1.0
if peak > 0.98:
    merged = merged / peak * 0.95

sf.write(OUT_WAV, merged.astype('float32'), SR)
dur = len(merged) / SR
print(f'\n合成总长 {dur:.1f}s = {dur/60:.2f} 分钟')

subprocess.run([FF, '-y', '-v', 'error', '-i', OUT_WAV, '-c:a', 'libmp3lame', '-b:a', '128k', OUT_MP3],
               capture_output=True)
if os.path.exists(OUT_MP3):
    print(f'已导出 {OUT_MP3}  ({os.path.getsize(OUT_MP3)/1048576:.1f} MB)')
else:
    print('mp3 导出失败')
