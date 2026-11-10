# -*- coding: utf-8 -*-
"""v6 看护：每 10 分钟检查一次，daemon 挂了自动重启；跑完自动出抽检报告。

由 Windows 计划任务每 10 分钟调用。
"""
import json
import os
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
STATUS = os.path.join(HERE, "status_v6.json")
LOG = os.path.join(HERE, "watchdog.log")
REPORT = os.path.join(HERE, "v6结果报告.md")
DAEMON = os.path.join(HERE, "v6_daemon.py")


def log(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M:%S"), msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def daemon_alive():
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*v6_daemon*' } | Measure-Object | "
             "Select-Object -ExpandProperty Count"],
            capture_output=True, text=True, timeout=60)
        return int((r.stdout or "0").strip() or 0) > 0
    except Exception:
        return False


def read_status():
    try:
        return json.load(open(STATUS, encoding="utf-8"))
    except Exception:
        return {"state": "unknown", "left": -1}


def counts():
    out = {}
    try:
        c = sqlite3.connect(r"E:\desktop\书库盘点\pilot_v2.db", timeout=30)
        for r in c.execute("select board,count(*) from split_items_v3 group by board"):
            out[r[0]] = r[1]
        out["_total"] = c.execute("select count(*) from split_items_v3").fetchone()[0]
        c.close()
    except Exception as e:
        out["_err"] = str(e)[:80]
    return out


def write_report():
    st = read_status()
    n = counts()
    labels = [("hook", "钩子"), ("dry", "干货"), ("case", "案例"),
              ("quote", "金句"), ("avoid", "避坑")]
    lines = ["# v6 全量拆解结果", "",
             "> 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M"), "",
             "状态：%s ｜ 剩余块：%s" % (st.get("state"), st.get("left")), "",
             "## 各板块产出", "", "| 板块 | 条数 |", "|---|---|"]
    for k, v in labels:
        lines.append("| %s | %s |" % (v, "{:,}".format(n.get(k, 0))))
    lines += ["| **合计** | **%s** |" % "{:,}".format(n.get("_total", 0)), "",
              "## 抽检样本", ""]
    c = sqlite3.connect(r"E:\desktop\书库盘点\pilot_v2.db", timeout=30)
    for k, v in labels:
        lines += ["### %s（随机 10 条）" % v, ""]
        for i, r in enumerate(c.execute(
                "select score,text,translation,title from split_items_v3 where board=? "
                "order by random() limit 10", (k,)), 1):
            tx = (r[1] or "").replace("\n", " ")[:160]
            lines.append("%d. [%g] %s" % (i, r[0], tx))
            if r[2]:
                lines.append("   - 译：%s" % r[2][:120])
            lines.append("   - 出处：《%s》" % (r[3] or "?")[:30])
        lines.append("")
    c.close()
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log("已写结果报告：" + REPORT)


def main():
    st = read_status()
    left = st.get("left", -1)
    state = st.get("state", "unknown")

    if left == 0 or state == "idle":
        if not os.path.exists(REPORT):
            log("检测到已跑完，生成报告")
            write_report()
        log("已跑完，无需动作")
        return

    if daemon_alive():
        log("daemon 正常，left=%s" % left)
        return

    log("daemon 不在运行（state=%s left=%s），重启" % (state, left))
    if os.path.exists(os.path.join(HERE, "STOP_V6")):
        log("存在 STOP_V6，不重启")
        return
    subprocess.Popen([PY, DAEMON], cwd=HERE,
                     creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
    log("已重启 daemon")


if __name__ == "__main__":
    # pythonw 下 sys.stdout 是 None，直接 reconfigure 会崩；计划任务里不能再弹黑框
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
