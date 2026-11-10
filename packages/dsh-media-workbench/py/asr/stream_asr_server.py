# -*- coding: utf-8 -*-
"""真流式语音识别服务（sherpa-onnx + paraformer-zh-streaming）。

和 speech_server.py（whisper 伪流式）的区别：
  whisper：收 4 秒音频 → 想 1.7 秒 → 蹦出一整段字
  这个  ：每 100ms 推一小段 → **立刻吐部分结果** → 字跟着嘴往外冒

接口（默认 8778，只监听 127.0.0.1）：
  GET  /health
  POST /open                      -> {"ok":true,"sid":"..."}
  POST /chunk?sid=xxx  body=PCM   -> {"ok":true,"text":"...","final":false}
  POST /close?sid=xxx             -> {"ok":true,"text":"..."}

body = 16kHz / mono / s16le 小端。
"""
import json
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

MODEL_DIR = r"E:\tools\asr\models\sherpa\sherpa-onnx-streaming-paraformer-bilingual-zh-en"
PORT = 8778
LOG = r"E:\tools\asr\logs\stream_asr.log"

if sys.stdout is None or sys.stderr is None:
    _n = open(os.devnull, "w")
    sys.stdout = sys.stdout or _n
    sys.stderr = sys.stderr or _n
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(m):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%m-%d %H:%M:%S ") + str(m) + "\n")
    except Exception:
        pass


_recognizer = None
_rec_lock = threading.Lock()


def get_recognizer():
    global _recognizer
    with _rec_lock:
        if _recognizer is not None:
            return _recognizer
        import sherpa_onnx
        enc = os.path.join(MODEL_DIR, "encoder.int8.onnx")
        dec = os.path.join(MODEL_DIR, "decoder.int8.onnx")
        tok = os.path.join(MODEL_DIR, "tokens.txt")
        for p in (enc, dec, tok):
            if not os.path.exists(p):
                raise RuntimeError("模型文件缺失: " + p)
        _recognizer = sherpa_onnx.OnlineRecognizer.from_paraformer(
            encoder=enc,
            decoder=dec,
            tokens=tok,
            num_threads=2,
            sample_rate=16000,
            feature_dim=80,
            decoding_method="greedy_search",
            debug=False,
            provider="cpu",
        )
        log("识别器加载完成")
        return _recognizer


_SESSIONS = {}
_SESS_LOCK = threading.Lock()


class Sess:
    def __init__(self):
        self.stream = None
        self.text = ""
        self.at = time.time()


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(b)))
        self.send_header("access-control-allow-origin", "*")
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "GET,POST,OPTIONS")
        self.send_header("access-control-allow-headers", "content-type")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            ok = os.path.exists(os.path.join(MODEL_DIR, "encoder.int8.onnx"))
            return self._send(200, {"ok": True, "model": ok, "sessions": len(_SESSIONS)})
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        sid = (q.get("sid") or [""])[0]
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n) if n else b""

        try:
            if u.path == "/open":
                rec = get_recognizer()
                s = Sess()
                s.stream = rec.create_stream()
                nid = uuid.uuid4().hex[:12]
                with _SESS_LOCK:
                    _SESSIONS[nid] = s
                    # 顺手清理 5 分钟没动的会话
                    now = time.time()
                    for k in [k for k, v in _SESSIONS.items() if now - v.at > 300]:
                        _SESSIONS.pop(k, None)
                return self._send(200, {"ok": True, "sid": nid})

            if u.path == "/chunk":
                with _SESS_LOCK:
                    s = _SESSIONS.get(sid)
                if not s:
                    return self._send(404, {"ok": False, "error": "会话不存在，重新 /open"})
                rec = get_recognizer()
                if body:
                    import array
                    arr = array.array("h")
                    arr.frombytes(body[: len(body) // 2 * 2])
                    samples = [x / 32768.0 for x in arr]
                    s.stream.accept_waveform(16000, samples)
                    s.at = time.time()
                while rec.is_ready(s.stream):
                    rec.decode_stream(s.stream)
                txt = rec.get_result(s.stream) or ""
                s.text = txt
                return self._send(200, {"ok": True, "text": txt, "final": False})

            if u.path == "/close":
                with _SESS_LOCK:
                    s = _SESSIONS.pop(sid, None)
                if not s:
                    return self._send(200, {"ok": True, "text": ""})
                rec = get_recognizer()
                try:
                    s.stream.accept_waveform(16000, [0.0] * 4800)  # 补 0.3s 静音，逼出尾巴
                    s.stream.input_finished()
                    while rec.is_ready(s.stream):
                        rec.decode_stream(s.stream)
                    txt = rec.get_result(s.stream) or s.text
                except Exception:
                    txt = s.text
                return self._send(200, {"ok": True, "text": txt})

            self._send(404, {"ok": False, "error": "not found"})
        except Exception as e:
            log("POST %s 出错: %s" % (self.path, e))
            self._send(500, {"ok": False, "error": str(e)[-300:]})


def main():
    log("=== 流式 ASR 服务启动 :%d ===" % PORT)
    get_recognizer()   # 预加载，第一次请求就不用等
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    srv.serve_forever()


if __name__ == "__main__":
    main()
