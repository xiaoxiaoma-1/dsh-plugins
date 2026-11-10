# -*- coding: utf-8 -*-
"""SoulX 主对谈 + 混音层：在检测到的静音处插入低音量插话、并把停顿拉长"""
import os, subprocess, numpy as np, soundfile as sf

PY = r'E:\tools\asr\.venv\Scripts\python.exe'
FF = r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
SRC = r'E:\tools\soulx-podcast\outputs\probe6.wav'
TMP = r'E:\desktop\media\_sx'
os.makedirs(TMP, exist_ok=True)
SR = 24000

d, sr = sf.read(SRC, dtype='float32')
if sr != SR:
    d = np.interp(np.linspace(0, 1, int(len(d) * SR / sr)), np.linspace(0, 1, len(d))).astype('float32')
if d.ndim > 1:
    d = d.mean(axis=1)

# 1) 找静音区（|x|<0.012 连续 >160ms）
th = 0.012
quiet = np.abs(d) < th
runs, i = [], 0
while i < len(quiet):
    if quiet[i]:
        j = i
        while j < len(quiet) and quiet[j]:
            j += 1
        if (j - i) > int(0.16 * SR):
            runs.append((i, j))
        i = j
    else:
        i += 1

# 2) 合成 4 个插话（用同一套音色里更轻的语气）
BC = ['嗯', '嗯哼', '啧', '哦']
bc_clips = []
for k, t in enumerate(BC):
    mp3 = os.path.join(TMP, 'bc%d.mp3' % k)
    wav = os.path.join(TMP, 'bc%d.wav' % k)
    subprocess.run([PY, '-m', 'edge_tts', '--voice', 'zh-CN-YunxiNeural', '--rate=-4%',
                    '--text', t, '--write-media', mp3], capture_output=True)
    subprocess.run([FF, '-y', '-i', mp3, '-ar', str(SR), '-ac', '1', wav], capture_output=True)
    c, _ = sf.read(wav, dtype='float32')
    bc_clips.append(c)

# 3) 在 4 个较长静音的中点插插话（音量 0.42），并把该处静音拉长 250ms
picks = sorted(runs, key=lambda r: -(r[1] - r[0]))[:4]
picks.sort()
ins = []
for idx, (s, e) in enumerate(picks):
    mid = (s + e) // 2
    ins.append((mid, bc_clips[idx % len(bc_clips)], 0.42, int(0.25 * SR)))

# 4) 重建时间轴（插入静音 → 平移后续样本）
out = d.copy()
shift = 0
for mid, clip, gain, padlen in ins:
    pos = mid + shift
    # 插静音
    out = np.concatenate([out[:pos], np.zeros(padlen, dtype='float32'), out[pos:]])
    shift += padlen
    # 叠插话（起点提前 60ms，让尾巴落在对方句尾之后）
    st = max(0, pos - int(0.06 * SR))
    en = min(len(out), st + len(clip))
    out[st:en] += clip[:en - st] * gain

peak = float(np.max(np.abs(out))) or 1.0
out = out / peak * 0.92
w = os.path.join(TMP, 'mix.wav')
sf.write(w, out, SR)
dst = r'E:\desktop\播客样音_SoulX混音版.mp3'
subprocess.run([FF, '-y', '-i', w, '-c:a', 'libmp3lame', '-b:a', '128k', dst], capture_output=True)
print('silences', len(runs), 'inserted', len(ins), 'dur', round(len(out) / SR, 1), 's |',
      round(os.path.getsize(dst) / 1024), 'KB', flush=True)
