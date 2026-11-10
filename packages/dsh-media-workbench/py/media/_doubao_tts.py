# -*- coding: utf-8 -*-
"""豆包语音合成2.0（Seed-TTS 2.0）：用 X-Api-Key 出双人对谈"""
import json, base64, os, sys, uuid, urllib.request, subprocess

KEY = 'dfa2d3f4-f69c-48ac-b0da-e3b54bccffe6'
URL = 'https://openspeech.bytedance.com/api/v3/tts/unidirectional'
OUT = r'E:\desktop\media\_db'
os.makedirs(OUT, exist_ok=True)

FEMALE = ['zh_female_vv_uranus_bigtts', 'zh_female_shuangkuaisisi_moon_bigtts', 'zh_female_tianmeixiaoyuan_moon_bigtts']
MALE = ['zh_male_beijingxiaoye_moon_bigtts', 'zh_male_yangguangqingnian_moon_bigtts',
        'zh_male_jingqiangkanye_moon_bigtts', 'zh_male_ahu_conversation_wvae_bigtts',
        'zh_male_lengkugege_emo_v2_mars_bigtts']


def synth(text, speaker):
    body = {'user': {'uid': 'podcast'}, 'req_params': {
        'text': text, 'speaker': speaker,
        'audio_params': {'format': 'mp3', 'sample_rate': 24000}}}
    h = {'Content-Type': 'application/json', 'X-Api-Key': KEY,
         'X-Api-Resource-Id': 'seed-tts-2.0', 'X-Api-Request-Id': str(uuid.uuid4())}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=h)
    try:
        r = urllib.request.urlopen(req, timeout=60)
    except Exception as e:
        try:
            return None, e.read().decode('utf-8', 'ignore')[:160]
        except Exception:
            return None, str(e)[:80]
    raw = r.read().decode('utf-8', 'ignore')
    # 可能是 NDJSON：取所有含 data 的行拼接
    audio = b''
    code = None
    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            j = json.loads(line)
        except Exception:
            continue
        if code is None:
            code = j.get('code')
        d = j.get('data')
        if d:
            audio += base64.b64decode(d)
    if not audio:
        return None, raw[:160]
    return audio, None


def pick(voices, text):
    for v in voices:
        a, err = synth(text, v)
        if a:
            return v, a
        print('  voice fail', v, err, flush=True)
    return None, None


f, _ = pick(FEMALE, '你好，这是测试。')
m, _ = pick(MALE, '好的，我也说一句。')
print('female voice:', f, '| male voice:', m, flush=True)
if not f or not m:
    sys.exit('音色都不可用')

TURNS = [
    (f, '诶，等一下。你这说法……我有点没听懂。'),
    (m, '嗯。'),
    (f, '粉丝越多，越难赚？这逻辑反了吧。'),
    (m, '呃……怎么说呢。一开始我也不信。'),
    (f, '嗯哼。'),
    (m, '真的，我跟人吵过。'),
    (f, '那你给我说说。'),
    (m, '我想想啊……小红书把账号，放在不同的池子里。一万粉，一个池子。'),
    (f, '嗯哼。'),
    (m, '十万粉，又是另一个。'),
    (f, '哦——所以池子越大，对手越狠？'),
    (m, '对。你在小池子里，能乱杀。进了大池子……就是被人乱杀。'),
    (f, '啧，那这么讲，涨粉还成负担了。'),
    (m, '呃，不是负担。是换赛道。你原来那套打法，在新池子里，它不认了。'),
]

files = []
for i, (v, t) in enumerate(TURNS):
    a, err = synth(t, v)
    if not a:
        print('turn fail', i, err, flush=True)
        continue
    p = os.path.join(OUT, '%02d.mp3' % i)
    with open(p, 'wb') as fp:
        fp.write(a)
    files.append(p)
print('turns ok:', len(files), '/', len(TURNS), flush=True)

gap = os.path.join(OUT, 'gap.mp3')
subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono',
                '-t', '0.28', gap], capture_output=True)
lst = os.path.join(OUT, 'list.txt')
with open(lst, 'w', encoding='utf-8') as fp:
    for p in files:
        fp.write("file '%s'\n" % p.replace('\\', '/'))
        fp.write("file '%s'\n" % gap.replace('\\', '/'))
res = subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lst,
                      '-c:a', 'libmp3lame', '-b:a', '128k',
                      r'E:\desktop\播客样音_豆包SeedTTS2.mp3'], capture_output=True)
print('merge rc', res.returncode, flush=True)
