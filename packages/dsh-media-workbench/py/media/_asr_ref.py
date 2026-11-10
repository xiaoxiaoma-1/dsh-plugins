# -*- coding: utf-8 -*-
"""转写参考音（重采样用 numpy interpolate，绕开 av 版本不兼容）"""
import numpy as np, soundfile as sf
from faster_whisper import WhisperModel

wav = r'E:\tools\soulx-podcast\example\audios\ruiqi_raw.wav'
d, sr = sf.read(wav, dtype='float32')
if d.ndim > 1:
    d = d.mean(axis=1)
if sr != 16000:
    n = int(len(d) * 16000 / sr)
    d = np.interp(np.linspace(0, len(d) - 1, n), np.arange(len(d)), d).astype('float32')

model = WhisperModel('small', device='cpu', compute_type='int8')
segs, info = model.transcribe(d, language='zh', vad_filter=True)
txt = ''.join(s.text for s in segs).strip()
print('TEXT:', txt, flush=True)
