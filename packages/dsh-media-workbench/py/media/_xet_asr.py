# -*- coding: utf-8 -*-
"""faster-whisper 转录（绕过 av 解码：先用 ffmpeg 解成 16k 单声道 PCM）"""
import json, os, site, subprocess, sys, tempfile, time

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')

# ctranslate2 需要 CUDA12 的 cublas/cudnn DLL，把 nvidia 包目录加入 DLL 搜索路径
try:
    import nvidia as _nv
    _base = os.path.dirname(_nv.__file__)
    for _sub in ('cublas/bin', 'cudnn/bin'):
        _p = os.path.join(_base, *_sub.split('/'))
        if os.path.isdir(_p):
            os.add_dll_directory(_p)
            os.environ['PATH'] = _p + os.pathsep + os.environ.get('PATH', '')
except Exception as _e:
    print('nvidia dll path skip:', _e, flush=True)

import numpy as np
from faster_whisper import WhisperModel

AUD = r'E:\desktop\media\_xet_audio'
TXT = r'E:\desktop\media\_xet_text'
os.makedirs(TXT, exist_ok=True)
MAN = r'E:\desktop\media\_xet_manifest.json'
FFMPEG = r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'

MODEL = os.environ.get('WMODEL', 'large-v3')
ONLY = os.environ.get('ONLY')

man = json.load(open(MAN, encoding='utf-8'))
todo = [m for m in man if m.get('ok') and m.get('file')]
if ONLY:
    todo = [m for m in todo if str(m['idx']) == str(ONLY)]

print('loading model', MODEL, flush=True)
t0 = time.time()
model = WhisperModel(MODEL, device='cuda', compute_type='int8_float16')
print('model ready %.1fs' % (time.time() - t0), flush=True)


def load_pcm(path):
    """ffmpeg -> 16k mono float32"""
    p = subprocess.run([FFMPEG, '-v', 'error', '-i', path, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'],
                       capture_output=True)
    if p.returncode != 0:
        raise RuntimeError('ffmpeg: ' + p.stderr.decode('utf-8', 'ignore')[:300])
    return np.frombuffer(p.stdout, np.int16).astype(np.float32) / 32768.0


def fmt(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
    return '%02d:%02d:%02d' % (h, m, s)


for rec in todo:
    path = os.path.join(AUD, rec['file'])
    if not os.path.exists(path):
        print('MISS', rec['file'], flush=True); continue
    base = os.path.splitext(rec['file'])[0]
    md_path = os.path.join(TXT, base + '.md')
    json_path = os.path.join(TXT, base + '.json')
    if os.path.exists(json_path):
        print('SKIP', base, flush=True); continue
    t1 = time.time()
    audio = load_pcm(path)
    segs, info = model.transcribe(
        audio, language='zh', beam_size=5, vad_filter=True,
        vad_parameters={'min_silence_duration_ms': 500},
        condition_on_previous_text=False,
        initial_prompt='以下是普通话课程讲解，包含自媒体、定位、流量、变现、账号、案例等词。',
    )
    rows = []
    for s in segs:
        txt = (s.text or '').strip()
        if txt:
            rows.append({'s': round(s.start, 2), 'e': round(s.end, 2), 't': txt})
    plain = ''.join(r['t'] for r in rows)
    dur = rows[-1]['e'] if rows else 0
    el = time.time() - t1
    md = ['# ' + rec['title'], '',
          '- 来源：小鹅通 · 小年自媒体系统课',
          '- 资源：' + rec['rid'],
          '- 时长：%s（%.0f 秒）' % (fmt(dur), dur),
          '- 字数：%d' % len(plain), '',
          '## 全文（去时间戳）', '', plain, '', '## 逐句（带时间戳）', '']
    md += ['[%s] %s' % (fmt(r['s']), r['t']) for r in rows]
    open(md_path, 'w', encoding='utf-8').write('\n'.join(md))
    json.dump({'idx': rec['idx'], 'rid': rec['rid'], 'title': rec['title'], 'duration': dur,
               'chars': len(plain), 'plain': plain, 'segments': rows},
              open(json_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    rec['chars'] = len(plain); rec['asr_sec'] = round(el, 1); rec['asr_dur'] = dur
    json.dump(man, open(MAN, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('ASR %s chars=%d dur=%.0fs cost=%.1fs %.1fx' % (base, len(plain), dur, el, dur / max(el, .1)), flush=True)

print('ALL DONE', flush=True)
