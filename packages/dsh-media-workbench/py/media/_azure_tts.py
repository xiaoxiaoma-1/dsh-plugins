# -*- coding: utf-8 -*-
"""Azure 语音合成样音：用法  python _azure_tts.py <KEY> <REGION>
默认读环境变量 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION
"""
import os, sys, time

KEY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('AZURE_SPEECH_KEY', '')
REGION = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('AZURE_SPEECH_REGION', 'eastasia')
if not KEY:
    print('缺少 KEY：python _azure_tts.py <KEY> <REGION>')
    raise SystemExit(1)

import azure.cognitiveservices.speech as speechsdk

# 双人对话：(说话人, 文本, 音色, 情感风格)
TURNS = [
    ('A', '诶，等一下，你这说法我有点没听懂啊。', 'zh-CN-XiaoxiaoNeural', 'unhappy'),
    ('B', '就是，粉丝越多，其实越难赚。', 'zh-CN-YunxiNeural', 'calm'),
    ('A', '不是，你、你这个逻辑反了吧？', 'zh-CN-XiaoxiaoNeural', 'unhappy'),
    ('B', '一开始我也不信，真的，我当时还跟人吵过。', 'zh-CN-YunxiNeural', 'friendly'),
    ('A', '那你给我说说，到底为啥。', 'zh-CN-XiaoxiaoNeural', 'calm'),
    ('B', '小红书把账号放在不同的池子里。一万粉一个池子，十万粉又是另一个。', 'zh-CN-YunxiNeural', 'calm'),
    ('A', '那我懂了，池子越大，对手越狠。啧，那这么讲，涨粉还成负担了。', 'zh-CN-XiaoxiaoNeural', 'unhappy'),
    ('B', '不是负担，是换赛道。你原来那套打法，在新池子里，它不认了。', 'zh-CN-YunxiNeural', 'calm'),
]

cfg = speechsdk.SpeechConfig(subscription=KEY, region=REGION)
cfg.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3)

files = []
t0 = time.time()
for i, (who, text, voice, style) in enumerate(TURNS):
    cfg.speech_synthesis_voice_name = voice
    out = r'E:\desktop\media\_az\%d.mp3' % i
    os.makedirs(r'E:\desktop\media\_az', exist_ok=True)
    audio = speechsdk.audio.AudioOutputConfig(filename=out)
    syn = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio)
    ssml = (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
        "xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='zh-CN'>"
        "<voice name='%s'><mstts:express-as style='%s'>%s</mstts:express-as></voice></speak>"
    ) % (voice, style, text)
    r = syn.speak_ssml_async(ssml).get()
    if r.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        print('失败', i, r.reason, r.cancellation_details.error_details if r.cancellation_details else '')
        raise SystemExit(2)
    files.append(out)
    print(who, i, 'ok', flush=True)

print('total', round(time.time() - t0, 1), 's', flush=True)
