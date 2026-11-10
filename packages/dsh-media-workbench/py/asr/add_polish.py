# -*- coding: utf-8 -*-
"""表达训练加：AI 润色（直通）+ 存到我的观点。"""
S = r"E:\desktop\media\mobile_server.py"
H = r"E:\desktop\media\mobile_page.html"

# ============ 后端 ============
srv = open(S, encoding="utf-8").read()

BE = '''

def api_speech_polish(text):
    """表达训练里的 AI 润色：直接给一段文字，返回润色版（不入库）"""
    text = (text or "").strip()
    if len(text) < 15:
        return {"ok": False, "error": "太短了，说几句再润色"}
    out, err = _gw_chat(POLISH_SYSTEM, "下面是他的原话，请润色：\\n\\n" + text, max_tokens=1600)
    if err:
        return {"ok": False, "error": "润不了：" + err}
    return {"ok": True, "text": (out or "").strip(), "orig": text}

'''

if "def api_speech_polish(" not in srv:
    a = "def api_view_polish(view_id):"
    srv = srv.replace(a, BE.strip("\n") + "\n\n" + a, 1)
    print("[后端] speech_polish 已加")

if '"/api/speech_polish"' not in srv:
    a = '            if u.path == "/api/ping":'
    srv = srv.replace(a,
        '            if u.path == "/api/speech_polish":\n'
        '                return self._send(200, json.dumps(api_speech_polish(body.get("text")), ensure_ascii=False))\n'
        '            if u.path == "/api/speech_toview":\n'
        '                return self._send(200, json.dumps(api_myview_add(body.get("text"), body.get("title")), ensure_ascii=False))\n', 1)
    # 上面替换可能把原来的 ping 行吃掉，补回来
    srv = srv.replace(
        '            if u.path == "/api/speech_toview":\n'
        '                return self._send(200, json.dumps(api_myview_add(body.get("text"), body.get("title")), ensure_ascii=False))\n'
        '            if u.path == "/api/train_prompt":',
        '            if u.path == "/api/speech_toview":\n'
        '                return self._send(200, json.dumps(api_myview_add(body.get("text"), body.get("title")), ensure_ascii=False))\n'
        '            if u.path == "/api/ping":\n'
        '                return self._send(200, json.dumps({"ok": True, "pong": True}, ensure_ascii=False))\n'
        '            if u.path == "/api/train_prompt":', 1)
    print("[后端] 路由已加")

open(S + ".bak-polish", "wb").write(open(S, "rb").read())
open(S, "wb").write(srv.encode("utf-8"))
print("后端写盘")
