# -*- coding: utf-8 -*-
"""拆解控制：start / pause / resume / cancel / status

给看板按钮用，也可以直接命令行跑：
    python split_ctl.py start
    python split_ctl.py pause
    python split_ctl.py cancel
    python split_ctl.py status
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = os.path.join(HERE, "STOP_SPLIT")
STATUS = os.path.join(HERE, "status.json")
DAEMON = os.path.join(HERE, "extract_daemon.py")
PY = sys.executable


def running():
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*extract_daemon*' } | "
             "Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=20)
        return out.stdout.strip() != ""
    except Exception:
        return False


def write_status(state, extra=None):
    d = {"state": state, "updated": time.strftime("%Y-%m-%d %H:%M:%S")}
    if os.path.exists(STATUS):
        try:
            d.update(json.load(open(STATUS, encoding="utf-8")))
        except Exception:
            pass
    d["state"] = state
    d["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if extra:
        d.update(extra)
    json.dump(d, open(STATUS, "w", encoding="utf-8"), ensure_ascii=False)


def start():
    if os.path.exists(STOP):
        os.remove(STOP)
    if running():
        write_status("running")
        return {"ok": True, "msg": "已经在跑", "state": "running"}
    subprocess.Popen([PY, DAEMON], cwd=HERE,
                     creationflags=0x08000000,  # CREATE_NO_WINDOW
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    write_status("running")
    return {"ok": True, "msg": "已启动", "state": "running"}


def pause():
    open(STOP, "w").close()
    write_status("paused")
    return {"ok": True, "msg": "已暂停（跑完当前这块就停）", "state": "paused"}


def cancel():
    """强制结束进程，并留下暂停标记"""
    open(STOP, "w").close()
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*extract_daemon*' } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
            capture_output=True, timeout=20)
    except Exception:
        pass
    write_status("paused")
    return {"ok": True, "msg": "已停止", "state": "paused"}


def status():
    d = {}
    if os.path.exists(STATUS):
        try:
            d = json.load(open(STATUS, encoding="utf-8"))
        except Exception:
            d = {}
    d["alive"] = running()
    if not d.get("state"):
        d["state"] = "idle"
    return d


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    fn = {"start": start, "pause": pause, "cancel": cancel, "resume": start, "status": status}.get(cmd)
    if not fn:
        print(json.dumps({"ok": False, "msg": "未知命令 " + cmd}, ensure_ascii=False))
        return
    print(json.dumps(fn(), ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
