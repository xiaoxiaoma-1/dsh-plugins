# -*- coding: utf-8 -*-
"""人味对谈：逐句合成 → numpy 混音（插话降音量+轻微重叠+不均匀停顿）"""
import os, subprocess, numpy as np, soundfile as sf

PY = r'E:\tools\asr\.venv\Scripts\python.exe'
FF = r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
TMP = r'E:\desktop\media\_mix'
os.makedirs(TMP, exist_ok=True)
SR = 24000

A = 'zh-CN-XiaoxiaoNeural'
B = 'zh-CN-YunxiNeural'

# (说话人, 文本, 语速, 类型, 之后停顿ms)
# 类型: main=正话, bc=听话反应(低音量,叠在对方句尾)
ITEMS = [
    (A, '诶，等一下。你这说法……我有点没听懂。', '+6%', 'main', 260),
    (B, '嗯。', '-4%', 'bc', 0),
    (A, '粉丝越多，越难赚？这逻辑反了吧。', '+10%', 'main', 420),
    (B, '呃……怎么说呢。一开始我也不信。', '-6%', 'main', 220),
    (A, '嗯哼。', '-4%', 'bc', 0),
    (B, '真的，我跟人吵过。', '-4%', 'main', 620),
    (A, '那你给我说说。', '+8%', 'main', 700),
    (B, '我想想啊……小红书把账号，放在不同的池子里。一万粉，一个池子。', '-8%', 'main', 300),
    (A, '嗯哼。', '-4%', 'bc', 0),
    (B, '十万粉，又是另一个。', '-8%', 'main', 520),
    (A, '哦——所以池子越大，对手越狠？', '+9%', 'main', 300),
    (B, '对。你在小池子里，能乱杀。', '-6%', 'main', 480),
    (A, '啧。', '-6%', 'bc', 0),
    (B, '进了大池子……就是被人乱杀。', '-8%', 'main', 560),
    (A, '那这么讲，涨粉还成负担了。', '+4%', 'main', 300),
    (B, '呃，不是负担。是换赛道。你原来那套打法，在新池子里，它不认了。', '-7%', 'main', 200),
]

wavs = []
for i, (v, t, rate, kind, gap) in enumerate(ITEMS):
    mp3 = os.path.join(TMP, '%02d.mp3' % i)
    wav = os.path.join(TMP, '%02d.wav' % i)
    subprocess.run([PY, '-m', 'edge_tts', '--voice', v, '--rate=' + rate, '--text', t,
                    '--write-media', mp3], capture_output=True)
    subprocess.run([FF, '-y', '-i', mp3, '-ar', str(SR), '-ac', '1', wav], capture_output=True)
    wavs.append(wav)

data = []
for w in wavs:
    d, sr = sf.read(w, dtype='float32')
    if sr != SR:
        d = np.interp(np.linspace(0, 1, int(len(d) * SR / sr)), np.linspace(0, 1, len(d)), d).astype('float32')
    data.append(d)

cursor = 0
MAIN_GAIN = 1.0
BC_GAIN = 0.42          # 听话反应必须明显小声
placements = []
for i, (v, t, rate, kind, gap) in enumerate(ITEMS):
    d = data[i]
    if kind == 'bc':
        # 叠在上一句结尾前 0.25s 到结束后 0.15s 之间
        start = cursor - int(0.25 * SR) - len(d) + int(0.15 * SR)
        start = max(0, start)
        gain = BC_GAIN
    else:
        start = cursor + int(gap * SR / 1000)
        gain = MAIN_GAIN
    placements.append((start, d, gain))
    if kind != 'bc':
        cursor = start + len(d)

total = max(s + len(d) for s, d, g in placements) + SR
buf = np.zeros(total, dtype='float32')
for s, d, g in placements:
    end = min(total, s + len(d))
    buf[s:end] += d[:end - s] * g

peak = float(np.max(np.abs(buf))) or 1.0
buf = buf / peak * 0.92
out_wav = os.path.join(TMP, 'mix.wav')
sf.write(out_wav, buf, SR)
out_mp3 = r'E:\desktop\播客样音_人味混音版.mp3'
subprocess.run([FF, '-y', '-i', out_wav, '-c:a', 'libmp3lame', '-b:a', '128k', out_mp3], capture_output=True)
print('dur', round(len(buf) / SR, 1), 's |', round(os.path.getsize(out_mp3) / 1024), 'KB', flush=True)
