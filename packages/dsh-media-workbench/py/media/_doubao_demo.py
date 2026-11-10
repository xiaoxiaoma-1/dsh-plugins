# -*- coding: utf-8 -*-
"""验证 Seed-TTS 2.0 质量：暂时只用已通的音色，出 6 句连贯口播（听质感）"""
import json, base64, os, uuid, urllib.request, subprocess

KEY = 'dfa2d3f4-f69c-48ac-b0da-e3b54bccffe6'
URL = 'https://openspeech.bytedance.com/api/v3/tts/unidirectional'
OUT = r'E:\desktop\media\_db2'
os.makedirs(OUT, exist_ok=True)
V = 'zh_female_vv_uranus_bigtts'

LINES = [
    '诶，等一下。你这说法……我有点没听懂。',
    '粉丝越多，越难赚？这逻辑反了吧。',
    '呃……怎么说呢。一开始我也不信，真的，我跟人吵过。',
    '小红书把账号，放在不同的池子里。一万粉，一个池子；十万粉，又是另一个。',
    '哦——所以池子越大，对手越狠？',
    '对。你在小池子里能乱杀，进了大池子……就是被人乱杀。',
]


def synth(text, speaker, resource='seed-tts-2.0'):
    body = {'user': {'uid': 'podcast'}, 'req_params': {
        'text': text, 'speaker': speaker,
        'audio_params': {'format': 'mp3', 'sample_rate': 24000}}}
    h = {'Content-Type': 'application/json', 'X-Api-Key': KEY,
         'X-Api-Resource-Id': resource, 'X-Api-Request-Id': str(uuid.uuid4())}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=h)
    try:
        r = urllib.request.urlopen(req, timeout=60)
    except Exception as e:
        try:
            return None, e.read().decode('utf-8', 'ignore')[:120]
        except Exception:
            return None, str(e)[:80]
    audio = b''
    for line in r.read().decode('utf-8', 'ignore').split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get('data'):
            audio += base64.b64decode(j['data'])
    return (audio, None) if audio else (None, 'empty')


files = []
for i, t in enumerate(LINES):
    a, err = synth(t, V)
    if not a:
        print('fail', i, err, flush=True)
        continue
    p = os.path.join(OUT, '%02d.mp3' % i)
    open(p, 'wb').write(a)
    files.append(p)
print('ok', len(files), flush=True)

gap = os.path.join(OUT, 'gap.mp3')
subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '0.28', gap], capture_output=True)
lst = os.path.join(OUT, 'list.txt')
with open(lst, 'w', encoding='utf-8') as fp:
    for p in files:
        fp.write("file '%s'\nfile '%s'\n" % (p.replace('\\', '/'), gap.replace('\\', '/')))
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c:a', 'libmp3lame', '-b:a', '128k',
                r'E:\desktop\播客样音_豆包SeedTTS2.mp3'], capture_output=True)
print('done', os.path.getsize(r'E:\desktop\播客样音_豆包SeedTTS2.mp3') // 1024, 'KB', flush=True)
