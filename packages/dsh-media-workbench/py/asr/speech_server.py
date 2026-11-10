# -*- coding: utf-8 -*-
"""口播训练 · 常驻语音识别服务

用途：浏览器边录边把 16k 单声道 PCM 发过来，这里用常驻内存的 faster-whisper 转文字。
常驻的原因：模型加载一次要几秒，每几秒重载一次不可行。

实测（Ryzen 5600X / CPU int8，每次调用会被 pad 到 30s 窗口）：
  small  4s 音频 -> 1.7s    8s -> 2.1s     （流式用这个）
  turbo  4s 音频 -> 6.7s    8s -> 7.0s     （收尾整段精转用这个）

启动：python speech_server.py [port]     默认 8777
接口：
  GET  /health
  POST /asr?m=small|turbo    body = raw PCM s16le / 16kHz / mono  -> {"ok":true,"text":"..."}
  POST /transcribe           body = {"wav":"<绝对路径>","m":"turbo"}
                             -> {"ok":true,"text":"...","duration":12.3,"segments":[{"start":..,"end":..,"text":".."}]}
                             用途：采集台转写复用这里已加载的模型，
                             不再新起进程抢内存（实测新进程在服务占 5.4G 时会 mkl_malloc 失败）

只监听 127.0.0.1。
"""
import json
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = r"E:\tools\asr\models"
MODELS = {
    "small": os.path.join(BASE, "small"),   # 模型较小，快
    "turbo": os.path.join(BASE, "turbo"),                  # 准确，慢
}

_loaded = {}


def get_model(name):
    name = name if name in MODELS else "small"
    if name in _loaded:
        return _loaded[name]
    from faster_whisper import WhisperModel
    path = MODELS[name]
    if not os.path.isdir(path):
        raise RuntimeError("模型目录不存在: " + path)
    # 流式用 small；turbo 只在小分片时才用得上，先按需加载
    _loaded[name] = WhisperModel(path, device="cpu", compute_type="int8", cpu_threads=6)
    return _loaded[name]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send({"ok": True, "loaded": list(_loaded.keys()), "models": list(MODELS.keys())})
        else:
            self._send({"ok": False, "error": "not found"}, 404)

    def _transcribe_file(self):
        """按路径转写一个 16k 单声道 wav，复用常驻模型"""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            req = json.loads(raw.decode("utf-8") or "{}")
            wav = req.get("wav") or ""
            name = req.get("m") or "turbo"
            if not wav or not os.path.exists(wav):
                self._send({"ok": False, "error": "wav 不存在: " + str(wav)}, 400)
                return
            import wave
            import numpy as np
            with wave.open(wav, "rb") as w:
                if w.getnchannels() != 1 or w.getframerate() != 16000:
                    self._send({"ok": False, "error": "需要 16k 单声道 wav"}, 400)
                    return
                buf = w.readframes(w.getnframes())
            audio = np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0
            t0 = time.time()
            model = get_model(name)
            segs, info = model.transcribe(
                audio, language="zh", beam_size=5, vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400),
                initial_prompt="以下是普通话口播内容，请使用简体中文并加标点。",
                condition_on_previous_text=False,
            )
            out = []
            for s in segs:
                txt = s.text.strip()
                if txt:
                    out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": txt})
            text = "".join(x["text"] for x in out)
            self._send({"ok": True, "text": text, "model": name,
                        "duration": round(float(getattr(info, "duration", 0) or 0), 2),
                        "segments": out, "ms": int((time.time() - t0) * 1000)})
        except Exception as e:
            traceback.print_exc()
            self._send({"ok": False, "error": str(e)[:300]}, 500)

    def do_POST(self):
        if self.path.startswith("/transcribe"):
            self._transcribe_file()
            return
        if not self.path.startswith("/asr"):
            self._send({"ok": False, "error": "not found"}, 404)
            return
        # 取模型名
        name = "small"
        if "m=" in self.path:
            name = self.path.split("m=", 1)[1].split("&")[0] or "small"
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            if len(raw) < 3200:  # 少于 0.1 秒，直接空
                self._send({"ok": True, "text": "", "ms": 0})
                return
            import numpy as np
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            t0 = time.time()
            model = get_model(name)
            segs, _info = model.transcribe(
                audio, language="zh", beam_size=1, vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300),
                initial_prompt="以下是普通话口播，请用简体中文加标点。",
                condition_on_previous_text=False,
            )
            text = "".join(s.text for s in segs).strip()
            self._send({"ok": True, "text": text, "model": name, "ms": int((time.time() - t0) * 1000)})
        except Exception as e:
            traceback.print_exc()
            self._send({"ok": False, "error": str(e)[:300]}, 500)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[speech] listening 127.0.0.1:{port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
