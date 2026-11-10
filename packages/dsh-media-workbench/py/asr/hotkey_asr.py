# -*- coding: utf-8 -*-
"""按住 F9 说话，松手把文字打进当前光标处。完全本地，不依赖微信。

依赖：流式服务 127.0.0.1:8778（stream_asr_server.py）+ keyboard / pyperclip / sounddevice

用法：pythonw hotkey_asr.py
      按住 F9 说话 → 松开 → 文字自动粘贴到当前焦点
      F10 退出
"""
import json
import os
import queue
import sys
import threading
import time
import urllib.request

import keyboard
import pyperclip
import sounddevice as sd

PORT = 8778
SR = 16000
CHUNK_MS = 100
HOTKEY = 'f9'
EXIT_KEY = 'f10'
LOG = r'E:\tools\asr\logs\hotkey_asr.log'

if sys.stdout is None or sys.stderr is None:
    _n = open(os.devnull, 'w')
    sys.stdout = sys.stdout or _n
    sys.stderr = sys.stderr or _n
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def log(m):
    line = time.strftime('%m-%d %H:%M:%S ') + str(m)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def post(path, data, ctype='application/octet-stream', timeout=30):
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (PORT, path), data=data, method='POST')
    req.add_header('Content-Type', ctype)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def service_ok():
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/health' % PORT, timeout=2) as r:
            return bool(json.loads(r.read().decode('utf-8')).get('ok'))
    except Exception:
        return False


rec_q = queue.Queue()
recording = False
stream = None
busy = False


def _cb(indata, frames, t, status):
    if recording:
        rec_q.put(bytes(indata))


def start_rec():
    global stream, recording
    while not rec_q.empty():
        rec_q.get_nowait()
    stream = sd.RawInputStream(samplerate=SR, channels=1, dtype='int16',
                               blocksize=int(SR * CHUNK_MS / 1000), callback=_cb)
    stream.start()
    recording = True


def stop_rec():
    global stream, recording
    recording = False
    if stream:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        stream = None


def worker(sid):
    """推流 + 收尾"""
    global busy
    text = ''
    started = time.time()
    try:
        while True:
            try:
                chunk = rec_q.get(timeout=0.2)
            except queue.Empty:
                if not recording:
                    break
                continue
            try:
                r = post('/chunk?sid=' + sid, chunk, timeout=10)
                t = (r.get('text') or '').strip()
                if t:
                    text = t
            except Exception as e:
                log('chunk err ' + repr(e)[:80])
        try:
            final = (post('/close?sid=' + sid, b'', timeout=30).get('text') or '').strip()
        except Exception:
            final = ''
        final = final or text
        log('done %.1fs: %s' % (time.time() - started, final))
        if final:
            pyperclip.copy(final)
            time.sleep(0.06)
            keyboard.send('ctrl+v')
    except Exception as e:
        log('worker err ' + repr(e)[:160])
    finally:
        stop_rec()
        busy = False


def on_down(e=None):
    global busy
    if busy:
        return
    if not service_ok():
        log('service down')
        return
    try:
        sid = post('/open', b'{}', 'application/json', timeout=5).get('sid')
    except Exception as ex:
        log('open err ' + repr(ex)[:80])
        return
    if not sid:
        log('no sid')
        return
    busy = True
    start_rec()
    log('rec start ' + sid)
    threading.Thread(target=worker, args=(sid,), daemon=True).start()


def on_up(e=None):
    if recording:
        recording = False  # worker 看到就收尾
        stop_rec()


def main():
    if not service_ok():
        log('warn: ASR 服务未就绪（8778），先启动 stream_asr_server.py')
    log('ready: 按住 %s 说话，松开粘贴；%s 退出' % (HOTKEY.upper(), EXIT_KEY.upper()))
    keyboard.on_press_key(HOTKEY, on_down)
    keyboard.on_release_key(HOTKEY, on_up)
    keyboard.wait(EXIT_KEY)
    log('exit')


if __name__ == '__main__':
    main()
