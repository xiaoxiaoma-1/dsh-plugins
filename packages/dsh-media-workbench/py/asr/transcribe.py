import sys, os, json, time, wave, glob, sysconfig

# ctranslate2 的 CUDA 后端需要 cublas / cudnn 的 dll，pip 装的 nvidia 包不在默认搜索路径里
# 注意：光 add_dll_directory 不够，ctranslate2 计算时用普通 LoadLibrary，必须同时塞进 PATH
if hasattr(os, "add_dll_directory"):
    _sp = sysconfig.get_paths()["purelib"]
    _dirs = glob.glob(os.path.join(_sp, "nvidia", "*", "bin"))
    for _d in _dirs:
        try:
            os.add_dll_directory(_d)
        except OSError:
            pass
    if _dirs:
        os.environ["PATH"] = os.pathsep.join(_dirs) + os.pathsep + os.environ.get("PATH", "")

import numpy as np
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
MODELS_DIR = r"E:\tools\asr\models"
# 显存/内存不够时 large-v3 会直接崩（mkl_malloc: failed to allocate memory），
# 所以按「够用就好」的顺序降级：先试 large-v3，失败换 turbo，再失败换 CPU。
_DEVICE = os.environ.get("ASR_DEVICE", "").strip().lower()
if _DEVICE == "cpu":
    # 用户在用电脑时不占 GPU（之前 84% 负载把抖音卡死过）
    CANDIDATES = [
        ("turbo", os.path.join(MODELS_DIR, "turbo"), "cpu", "int8"),
    ]
elif _DEVICE == "cuda":
    CANDIDATES = [
        ("turbo", os.path.join(MODELS_DIR, "turbo"), "cuda", "float16"),
        ("turbo", os.path.join(MODELS_DIR, "turbo"), "cpu", "int8"),
    ]
else:
    CANDIDATES = [
        ("turbo", os.path.join(MODELS_DIR, "turbo"), "cuda", "float16"),
        ("turbo", os.path.join(MODELS_DIR, "turbo"), "cpu", "int8"),
    ]


def load_model():
    last = None
    for name, path, dev, ct in CANDIDATES:
        if not os.path.isdir(path):
            print(f"[skip] {name}/{dev}: 目录不存在 {path}", flush=True)
            continue
        try:
            m = WhisperModel(path, device=dev, compute_type=ct)
            print(f"[model] {name} on {dev}/{ct}", flush=True)
            return m
        except Exception as e:
            last = e
            print(f"[warn] {name}/{dev} 加载失败: {str(e)[:160]}", flush=True)
    raise RuntimeError("所有模型都加载失败: %s" % last)


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1, "需要单声道"
        assert w.getframerate() == SAMPLE_RATE, "需要 16k 采样率"
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

def fmt_srt(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def main():
    wav = sys.argv[1]
    base = os.path.splitext(wav)[0]
    t0 = time.time()
    model = load_model()
    t_load = time.time() - t0
    print(f"[model] loaded in {t_load:.1f}s", flush=True)

    audio = read_wav(wav)
    print(f"[audio] {len(audio)/SAMPLE_RATE:.1f}s", flush=True)

    segments, info = model.transcribe(
        audio,
        language="zh",
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400),
        initial_prompt="以下是普通话口播内容，请使用简体中文并加标点。",
        condition_on_previous_text=False,
    )

    segs = []
    for s in segments:
        txt = s.text.strip()
        if not txt:
            continue
        segs.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": txt})
        print(f"[{fmt_srt(s.start)}] {txt}", flush=True)

    t_asr = time.time() - t0
    print(f"[done] {len(segs)} segments, audio={info.duration:.1f}s, elapsed={t_asr:.1f}s, "
          f"rtf={t_asr/max(info.duration,1):.3f}", flush=True)

    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(s["text"] for s in segs))

    with open(base + ".srt", "w", encoding="utf-8") as f:
        for i, s in enumerate(segs, 1):
            f.write(f"{i}\n{fmt_srt(s['start'])} --> {fmt_srt(s['end'])}\n{s['text']}\n\n")

    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump({"duration": info.duration, "language": info.language,
                   "elapsed": round(t_asr, 1), "segments": segs}, f, ensure_ascii=False, indent=2)

    print("[out]", base + ".txt", flush=True)

if __name__ == "__main__":
    main()
