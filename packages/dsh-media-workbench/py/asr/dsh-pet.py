# -*- coding: utf-8 -*-
"""
dsh-pet.py —— 桌面宠物（独立进程）

1:1 复刻 DSH 内部悬浮球（dsh-bubble）的样式：
  · 54×54 深色玻璃球，径向渐变（左上偏亮）
  · 两只白色椭圆眼睛（9×12，间距 7）
  · 眨眼动画
  · 任务运行时球外一圈金色进度环
  · 右上角金色徽标显示在跑几个

★ 关键：tkinter 的 Canvas 背景不透明，圆球会被方形窗口切出直角。
   用 Windows 的 -transparentcolor 把背景色键掉，球才是真的圆。

截图交互（正常截图工具的样子）：
  · 全屏灰化，框内显示原亮度
  · 框内按住拖 = 移动框；框边拖 = 调整大小；框外拖 = 重画
  · 双击框内 = 确认 → 写 latest.txt → DSH 自动填进输入框
  · Esc 取消

启动：pythonw.exe dsh-pet.py
"""

import os
import sys
import time
import json
import math
import threading
import urllib.request
import tkinter as tk

try:
    from PIL import ImageGrab, ImageTk, Image, ImageDraw
except Exception:
    sys.exit(1)

OUT_DIR = r"E:\desktop\shots"
LATEST = os.path.join(OUT_DIR, "latest.txt")
BALL = 54          # 球本身直径
PAD = 6            # 四周留白（给徽标、进度环）
CANVAS = BALL + PAD * 2   # 画布 66，球居中
MARGIN = 12

# 抠色键（跟球体任何颜色都不撞）
KEY = "#010203"

# 浅色主题（用户当前的 DSH 主题）
BG_BASE = "#26262C"      # 球主体：黑色
BG_DARK = "#101014"      # 外沿更深
BG_HI = "#4A4A54"        # 左上高光（黑球上的浅灰反光）
EYE = "#F6F2E9"          # 眼珠：白色
BRAND = "#D9A94A"
RING = "#E3BA63"
BADGE_TXT = "#1A1A1A"


def ensure_dir():
    os.makedirs(OUT_DIR, exist_ok=True)


def fmt_ms(ms):
    s = int(ms / 1000)
    if s < 60:
        return "%d秒" % s
    m = s // 60
    if m < 60:
        return "%d分%d秒" % (m, s % 60)
    return "%d小时%d分" % (m // 60, m % 60)


def _h(c):
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _mix(c1, c2, t):
    r1, g1, b1 = _h(c1)
    r2, g2, b2 = _h(c2)
    return "#%02X%02X%02X" % (
        int(r1 * (1 - t) + r2 * t),
        int(g1 * (1 - t) + g2 * t),
        int(b1 * (1 - t) + b2 * t),
    )


def find_dsh_port():
    ports = []
    try:
        import subprocess
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
             "Where-Object { $_.LocalPort -ge 50000 -and $_.LocalPort -le 66000 } | "
             "Select-Object -ExpandProperty LocalPort"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            timeout=8, creationflags=0x08000000,
        ).stdout or ""
        for line in out.split():
            try:
                ports.append(int(line))
            except Exception:
                pass
    except Exception:
        pass
    for p in ports:
        try:
            req = urllib.request.Request("http://127.0.0.1:%d/dsh-bubble/status" % p)
            with urllib.request.urlopen(req, timeout=1.0) as r:
                if r.status == 200:
                    json.loads(r.read().decode("utf-8"))
                    return p
        except Exception:
            continue
    return None


def build_ball_image(size, radius_ratio=0.30):
    """
    圆角矩形玻璃球：径向渐变（左上偏亮）+ 圆角遮罩，4 倍超采样抗锯齿。
    对应 DSH 原版的：
      background: radial-gradient(circle at 38% 30%, <高光> 0%, <主体> 58%, <暗边> 100%)
      border-radius: 50%
    """
    SS = 4
    S = size * SS
    rad = int(size * radius_ratio * SS)

    # ---- 1. 径向渐变（小图算，再放大，省时间）----
    G = 48
    small = Image.new("L", (G, G), 0)
    px = small.load()
    hx, hy = 0.38 * G, 0.30 * G          # 高光圆心（对应 circle at 38% 30%）
    maxd = (max(hx, G - hx) ** 2 + max(hy, G - hy) ** 2) ** 0.5
    for y in range(G):
        for x in range(G):
            d = (((x - hx) ** 2 + (y - hy) ** 2) ** 0.5) / maxd
            d = min(1.0, d)
            px[x, y] = int(255 * (1.0 - d) ** 1.6)
    grad = small.resize((S, S), Image.LANCZOS)

    # ---- 2. 三层颜色合成：暗边 → 主体 → 高光 ----
    dark = Image.new("RGBA", (S, S), _h(BG_DARK) + (255,))
    base = Image.new("RGBA", (S, S), _h(BG_BASE) + (255,))
    hi = Image.new("RGBA", (S, S), _h(BG_HI) + (255,))

    img = Image.composite(base, dark, grad)
    img = Image.composite(hi, img, grad.point(lambda p: int(max(0, p - 150) * 1.7)))

    # ---- 3. 圆角遮罩 ----
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=rad, fill=255)
    # ---- 3b. 不用 alpha：mask 一刀切 + 键色填充，边缘绝不产生过渡色 ----
    mask = mask.point(lambda p: 255 if p > 128 else 0)
    out = Image.new("RGB", (S, S), _h(KEY))
    out.paste(img.convert("RGB"), (0, 0), mask)

    # ---- 4. 输出 ----
    return out.resize((size, size), Image.NEAREST)


# ============================================================ 球
class Pet:
    def __init__(self):
        self.port = None
        self.status = {"running": [], "runningCount": 0, "done": []}
        self.pod = {}
        self.panel = None
        self.shot = None
        self._drag = None
        self._moved = False
        self.blink = False
        self._blink_job = None
        self.eye_dx = 0.0
        self.eye_dy = 0.0
        self.poke = False
        self.scale = 1.0
        self._scale_cache = {}
        self._poking = False
        self._body_sig = None
        self._time_labels = []
        self._fail = 0

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        # ★ 关键：键掉背景色，球才是真的圆
        try:
            self.root.attributes("-transparentcolor", KEY)
        except Exception:
            pass
        self.root.configure(bg=KEY)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.x = sw - CANVAS - MARGIN
        self.y = sh - CANVAS - MARGIN - 80
        self.root.geometry("%dx%d+%d+%d" % (CANVAS, CANVAS, self.x, self.y))

        self.cv = tk.Canvas(self.root, width=CANVAS, height=CANVAS, bg=KEY,
                            highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)

        for w in (self.root, self.cv):
            w.bind("<ButtonPress-1>", self.on_press)
            w.bind("<B1-Motion>", self.on_drag)
            w.bind("<ButtonRelease-1>", self.on_release)
            w.bind("<Button-3>", lambda e: self.toggle_panel())

        self.build_once()
        threading.Thread(target=self.poll_loop, daemon=True).start()
        self.root.after(300, self.tick)
        self.root.after(60, self.update_eye)
        self.schedule_blink()

    # -------- 画球
    def build_once(self):
        """创建球的所有元素（只做一次）。之后只移动，不重建 —— 这样才丝滑。"""
        c = self.cv
        c.delete("all")
        self._ball_img = build_ball_image(CANVAS)
        self._ball_tk = ImageTk.PhotoImage(self._ball_img)
        self._scale_cache[1.0] = self._ball_tk
        self._i_ball = c.create_image(0, 0, anchor="nw", image=self._ball_tk)
        self._i_ring = None          # 金色环（有任务才画）
        self._i_eye_l = c.create_oval(0, 0, 0, 0, fill=EYE, outline="")
        self._i_eye_r = c.create_oval(0, 0, 0, 0, fill=EYE, outline="")
        self._i_badge = c.create_oval(0, 0, 0, 0, fill=BRAND, outline="",
                                      state="hidden")
        self._i_badge_t = c.create_text(0, 0, text="", fill=BADGE_TXT,
                                        font=("Microsoft YaHei UI", 9, "bold"),
                                        state="hidden")
        self.move_eyes(force=True)

    def ball_tk_at(self, scale):
        """按比例生成球图（居中贴回 CANVAS 画布，边角保持键色，边缘绝不发脏）"""
        key = round(scale, 3)
        hit = self._scale_cache.get(key)
        if hit is not None:
            return hit
        n = max(10, int(round(BALL * scale)))
        img = build_ball_image(n)
        canvas = Image.new("RGB", (CANVAS, CANVAS), _h(KEY))
        off = (CANVAS - n) // 2
        canvas.paste(img, (off, off))
        t = ImageTk.PhotoImage(canvas)
        self._scale_cache[key] = t
        return t

    def apply_scale(self, s):
        self.scale = s
        try:
            self.cv.itemconfigure(self._i_ball, image=self.ball_tk_at(s))
        except Exception:
            return
        self.move_eyes()

    def do_poke(self):
        """点一下球：弹一下（缩放序列），给个手感回执"""
        if self._poking:
            return
        self._poking = True
        seq = [0.84, 1.10, 0.93, 1.04, 1.0]

        def step(i):
            if i >= len(seq):
                self._poking = False
                return
            try:
                self.apply_scale(seq[i])
            except Exception:
                self._poking = False
                return
            self.root.after(40, lambda: step(i + 1))

        step(0)

    def move_eyes(self, force=False):
        """只改眼睛坐标 —— 60ms 一次也没有闪烁"""
        c = self.cv
        cx = cy = CANVAS / 2.0
        s = self.scale
        ew, eh, gap = 9.5 * s, (2.5 if self.blink else 13.0) * s, 7.5 * s
        dx, dy = self.eye_dx * s, self.eye_dy * s
        ey0 = cy - eh / 2.0 + dy
        c.coords(self._i_eye_l, cx - gap / 2 - ew + dx, ey0,
                 cx - gap / 2 + dx, ey0 + eh)
        c.coords(self._i_eye_r, cx + gap / 2 + dx, ey0,
                 cx + gap / 2 + ew + dx, ey0 + eh)

    def sync_status_art(self):
        """只更新「环 + 徽标」这类随状态变的东西"""
        c = self.cv
        n = int(self.status.get("runningCount") or 0)
        cx = cy = CANVAS / 2.0
        R = BALL / 2.0

        if n <= 0:
            if self._i_ring:
                c.delete(self._i_ring)
                self._i_ring = None
            c.itemconfigure(self._i_badge, state="hidden")
            c.itemconfigure(self._i_badge_t, state="hidden")
            return

        # 环：预建 72 段，只改 state（不反复 delete/crate，否则卡）
        TOTAL = 72
        if self._i_ring is None:
            self._i_ring = []
            rr = R - 0.5
            for k in range(TOTAL):
                a0 = math.radians(-90 + k * (360.0 / TOTAL))
                a1 = math.radians(-90 + (k + 1.1) * (360.0 / TOTAL))
                self._i_ring.append(c.create_line(
                    cx + rr * math.cos(a0), cy + rr * math.sin(a0),
                    cx + rr * math.cos(a1), cy + rr * math.sin(a1),
                    fill=RING, width=2.2, capstyle="round", state="hidden"))
        cnt = int(TOTAL * min(1.0, n / 4.0))
        for k, seg in enumerate(self._i_ring):
            c.itemconfigure(seg, state=("normal" if k < cnt else "hidden"))

        # 徽标
        d = 17
        bx = CANVAS - d - 1
        by = 1
        c.coords(self._i_badge, bx, by, bx + d, by + d)
        c.coords(self._i_badge_t, bx + d / 2, by + d / 2 + 0.5)
        c.itemconfigure(self._i_badge, state="normal")
        c.itemconfigure(self._i_badge_t, state="normal")
        c.itemconfigure(self._i_badge_t, text=str(n))

    def set_blink(self, on):
        self.blink = on
        self.move_eyes()

    def update_eye(self):
        """按 DSH 原版逻辑：眼睛朝鼠标方向偏移，距离 150px 内线性，最大 3.2px"""
        try:
            mx, my = self.root.winfo_pointerxy()
            cx = self.x + CANVAS / 2.0
            cy = self.y + CANVAS / 2.0
            ddx = mx - cx
            ddy = my - cy
            length = (ddx * ddx + ddy * ddy) ** 0.5
            if length < 0.001:
                self.eye_dx = self.eye_dy = 0.0
            else:
                k = min(1.0, length / 150.0) * 3.2
                self.eye_dx = ddx / length * k
                self.eye_dy = ddy / length * k
        except Exception:
            pass
        try:
            self.move_eyes()
        except Exception:
            pass
        self.root.after(33, self.update_eye)

    def schedule_blink(self):
        self._blink_job = self.root.after(3400 + int(time.time() * 13) % 2800, self.do_blink)

    def do_blink(self):
        self.set_blink(True)
        self.root.after(115, self._unblink)

    def _unblink(self):
        self.set_blink(False)
        self.schedule_blink()

    # -------- 拖动 / 点击
    def on_press(self, e):
        self._drag = (e.x_root - self.x, e.y_root - self.y)
        self._moved = False

    def on_drag(self, e):
        if not self._drag:
            return
        nx = e.x_root - self._drag[0]
        ny = e.y_root - self._drag[1]
        if abs(nx - self.x) > 3 or abs(ny - self.y) > 3:
            self._moved = True
        self.x, self.y = nx, ny
        self.root.geometry("+%d+%d" % (nx, ny))
        if self.panel:
            self.place_panel()

    def on_release(self, e):
        was = self._moved
        self._drag = None
        if not was:
            self.do_poke()
            self.toggle_panel()

    # -------- 轮询
    def poll_loop(self):
        """连上时 3 秒一刷；连不上时退避到 30 秒，绝不每 3 秒去起一个 powershell"""
        while True:
            try:
                if self.port is None:
                    self.port = find_dsh_port()
                if self.port:
                    req = urllib.request.Request(
                        "http://127.0.0.1:%d/dsh-bubble/status" % self.port)
                    with urllib.request.urlopen(req, timeout=2) as r:
                        j = json.loads(r.read().decode("utf-8"))
                        if j.get("ok"):
                            self.status = j
                            self._fail = 0
                        else:
                            self.port = None
                            self._fail += 1
                    # 顺手拉一下播客播放状态（面板上的播客条靠它）
                    try:
                        req2 = urllib.request.Request(
                            "http://127.0.0.1:%d/podcast/state" % self.port)
                        with urllib.request.urlopen(req2, timeout=1.5) as r2:
                            self.pod = json.loads(r2.read().decode("utf-8"))
                    except Exception:
                        pass
                else:
                    self.status = {"running": [], "runningCount": 0, "done": []}
                    self._fail += 1
            except Exception:
                self.port = None
                self._fail += 1
            delay = 3
            if self._fail:
                delay = min(30, 3 * (2 ** min(self._fail - 1, 4)))
            time.sleep(delay)

    def tick(self):
        try:
            self.sync_status_art()
        except Exception:
            pass
        if self.panel:
            try:
                if self.panel.winfo_exists():
                    self.render_body()
                    self.update_podbar()
            except Exception:
                pass
        self.root.after(120, self.tick)

    # -------- 播客
    def update_podbar(self):
        bar = getattr(self, "podbar", None)
        if not bar:
            return
        try:
            if not bar.winfo_exists():
                return
        except Exception:
            return
        p = self.pod or {}
        has = bool(p.get("hasSrc"))
        mapped = bool(bar.winfo_ismapped())
        if not has:
            if mapped:
                try:
                    bar.pack_forget()
                except Exception:
                    pass
            return
        if not mapped:
            try:
                bar.pack(fill="x", padx=12, pady=(4, 0),
                         before=getattr(self, "foot", None))
            except Exception:
                pass
        t = (p.get("title") or "播客").strip()
        t = os.path.basename(t) if ("/" in t or "\\" in t) else t
        if len(t) > 13:
            t = t[:13] + "…"
        playing = bool(p.get("playing"))
        try:
            self.pod_lbl.configure(text=("暂停中 · " if not playing else "播放中 · ") + t)
            self.pod_btn.configure(text="暂停" if playing else "播放")
        except Exception:
            pass

    def pod_toggle(self):
        threading.Thread(target=self._pod_post, args=("toggle",), daemon=True).start()
        self.root.after(700, self.poll_pod_once)

    def _pod_post(self, action):
        if not self.port:
            return
        try:
            data = json.dumps({"action": action}).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:%d/podcast/ctl" % self.port,
                data=data, headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as r:
                r.read()
        except Exception:
            pass

    def poll_pod_once(self):
        if not self.port:
            return
        def work():
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:%d/podcast/state" % self.port)
                with urllib.request.urlopen(req, timeout=1.5) as r:
                    self.pod = json.loads(r.read().decode("utf-8"))
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    # -------- 面板
    def toggle_panel(self):
        if self.panel and self.panel.winfo_exists():
            self.close_panel()
        else:
            self.open_panel()

    def place_panel(self):
        """按球当前位置重新摆面板（球拖动时面板跟着走）"""
        if not self.panel or not self.panel.winfo_exists():
            return
        try:
            W = self.panel.winfo_width()
            H = self.panel.winfo_height()
            if W <= 1:
                W = 340
            if H <= 1:
                H = 260
            # 用虚拟桌面（多屏）边界，不用主屏
            vx = int(self.root.winfo_vrootx())
            vy = int(self.root.winfo_vrooty())
            vw = int(self.root.winfo_vrootwidth())
            vh = int(self.root.winfo_vrootheight())
            x = self.x + CANVAS - W
            x = max(vx + 8, min(x, vx + vw - W - 8))
            y = self.y - H - 6
            if y < vy + 8:
                y = min(self.y + CANVAS + 6, vy + vh - H - 8)
            self.panel.geometry("+%d+%d" % (x, y))
        except Exception:
            pass

    def close_panel(self):
        if self.panel:
            try:
                self.panel.destroy()
            except Exception:
                pass
            self.panel = None

    def open_panel(self):
        if self.panel and self.panel.winfo_exists():
            return
        W = 340
        sw = self.root.winfo_screenwidth()
        x = max(int(self.root.winfo_vrootx()) + 8, min(self.x + CANVAS - W, int(self.root.winfo_vrootx()) + int(self.root.winfo_vrootwidth()) - W - 8))

        self.panel = tk.Toplevel(self.root)
        self.panel.overrideredirect(True)
        self.panel.attributes("-topmost", True)
        self.panel.configure(bg=BG_BASE)

        wrap = tk.Frame(self.panel, bg=_mix(BRAND, BG_BASE, 0.70), padx=1, pady=1)
        wrap.pack(fill="both", expand=True)
        inner = tk.Frame(wrap, bg=BG_BASE)
        inner.pack(fill="both", expand=True)

        head = tk.Frame(inner, bg=BG_BASE)
        head.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(head, text="任务", bg=BG_BASE, fg="#ECECEE",
                 font=("Microsoft YaHei UI", 12, "bold")).pack(side="left")
        xb = tk.Label(head, text="×", bg=BG_BASE, fg="#9D9DA3", cursor="hand2",
                      font=("Microsoft YaHei UI", 15))
        xb.pack(side="right")
        xb.bind("<Button-1>", lambda e: self.close_panel())

        self.body = tk.Frame(inner, bg=BG_BASE)
        self.body.pack(fill="both", expand=True, padx=12)
        self._body_sig = None          # 新面板 = 新 body，必须重建一次
        self.render_body(force=True)

        # 播客条：只有真在放音频时才显示（没音频就整条不占位）
        pod_bg = _mix("#FFFFFF", BG_BASE, 0.97)
        self.podbar = tk.Frame(inner, bg=pod_bg)
        self.pod_lbl = tk.Label(self.podbar, text="", bg=pod_bg, fg="#D8D8DE",
                                anchor="w", font=("Microsoft YaHei UI", 10))
        self.pod_lbl.pack(side="left", fill="x", expand=True, padx=(9, 4), pady=6)
        self.pod_btn = self.mkbtn(self.podbar, "播放", self.pod_toggle)
        self.pod_btn.pack(side="right", padx=(0, 6), pady=4)

        foot = tk.Frame(inner, bg=BG_BASE)
        self.foot = foot
        foot.pack(fill="x", padx=12, pady=(6, 9))
        self.update_podbar()
        self.mkbtn(foot, "截图", self.shoot, primary=True).pack(fill="x", pady=(0, 5))
        row = tk.Frame(foot, bg=BG_BASE)
        row.pack(fill="x")
        self.mkbtn(row, "退出", self.quit).pack(fill="x")
        tk.Label(foot, text="左键或右键点球都能打开这个面板", bg=BG_BASE, fg="#8B8B93",
                 font=("Microsoft YaHei UI", 10), anchor="w").pack(fill="x", pady=(7, 0))

        self.panel.update_idletasks()
        h = self.panel.winfo_reqheight()
        y = max(8, self.y - h - 6)
        self.panel.geometry("%dx%d+%d+%d" % (W, h, x, y))

    def mkbtn(self, parent, text, cmd, primary=False):
        bg = BRAND if primary else _mix("#FFFFFF", BG_BASE, 0.94)
        fg = BADGE_TXT if primary else "#E2E2E6"
        b = tk.Label(parent, text=text, bg=bg, fg=fg,
                     font=("Microsoft YaHei UI", 10, "bold" if primary else "normal"),
                     pady=6, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        hi = "#E8C679" if primary else _mix("#FFFFFF", BG_BASE, 0.88)
        b.bind("<Enter>", lambda e: b.configure(bg=hi))
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        return b

    def body_signature(self):
        st = self.status or {}
        running = st.get("running") or []
        done = st.get("done") or []
        return (
            self.port,
            tuple((r.get("id") or "", (r.get("title") or "").strip()) for r in running[:4]),
            tuple(((d.get("title") or "").strip(), d.get("at") or 0)
                  for d in list(reversed(done))[:3]),
        )

    def update_times(self):
        running = (self.status or {}).get("running") or []
        for lbl, i in self._time_labels:
            try:
                if i < len(running):
                    lbl.configure(text=fmt_ms(running[i].get("ms", 0)))
            except Exception:
                pass

    def render_body(self, force=False):
        """只在「任务列表真的变了」时重建。之前每 120ms 全量 destroy 重建，
        结果面板一直闪、按钮还没按下去就被销毁 —— 点了没反应。"""
        if not self.body or not self.body.winfo_exists():
            return
        sig = self.body_signature()
        if not force and sig == self._body_sig:
            self.update_times()
            return
        self._body_sig = sig
        self._time_labels = []
        for w in self.body.winfo_children():
            w.destroy()

        st = self.status or {}
        running = st.get("running") or []
        done = st.get("done") or []

        if self.port is None:
            tk.Label(self.body, text="没连上 DSH", bg=BG_BASE, fg="#E2665E",
                     font=("Microsoft YaHei UI", 11), anchor="w").pack(fill="x", pady=4)
            return
        if not running and not done:
            tk.Label(self.body, text="现在没有任务", bg=BG_BASE, fg="#8B8B93",
                     font=("Microsoft YaHei UI", 11), anchor="w").pack(fill="x", pady=6)
            return

        for i, r in enumerate(running[:4]):
            card_bg = _mix("#FFFFFF", BG_BASE, 0.96)
            card = tk.Frame(self.body, bg=card_bg)
            card.pack(fill="x", pady=3)
            tk.Frame(card, bg=_mix(BRAND, "#FFFFFF", 0.25), width=2).pack(side="left", fill="y")
            box = tk.Frame(card, bg=card_bg)
            box.pack(fill="x", padx=7, pady=6)
            rw = tk.Frame(box, bg=card_bg)
            rw.pack(fill="x")
            t = (r.get("title") or "").strip() or "未命名对话"
            tk.Label(rw, text=t, bg=card_bg, fg="#E2E2E6", anchor="w",
                     font=("Microsoft YaHei UI", 11)).pack(side="left")
            tl = tk.Label(rw, text=fmt_ms(r.get("ms", 0)), bg=card_bg, fg="#8B8B93",
                          font=("Microsoft YaHei UI", 10))
            tl.pack(side="right")
            self._time_labels.append((tl, i))

        for d in list(reversed(done))[:3]:
            card_bg = _mix("#FFFFFF", BG_BASE, 0.96)
            card = tk.Frame(self.body, bg=card_bg)
            card.pack(fill="x", pady=3)
            tk.Frame(card, bg=_mix("#78DC8C", "#FFFFFF", 0.25), width=2).pack(side="left", fill="y")
            box = tk.Frame(card, bg=card_bg)
            box.pack(fill="x", padx=7, pady=6)
            t = (d.get("title") or "").strip() or "有一项任务"
            tk.Label(box, text="%s 已完成" % t, bg=card_bg, fg="#78DC8C", anchor="w",
                     font=("Microsoft YaHei UI", 11), wraplength=270,
                     justify="left").pack(fill="x")

    # -------- 功能
    def shoot(self):
        self.close_panel()
        self.root.withdraw()
        self.root.after(220, self._grab)

    def _grab(self):
        try:
            img = ImageGrab.grab(all_screens=True)
        except Exception:
            self.root.deiconify()
            return
        self.root.deiconify()
        self.shot = Shot(img, self)

    def quit(self):
        self.close_panel()
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        ensure_dir()
        self.root.mainloop()


# ============================================================ 截图
class Shot:
    """全屏灰化，框内原亮度。框内拖=移动，框边拖=缩放，框外拖=重画，双击框内=确认，Esc=取消。"""

    EDGE = 6

    def __init__(self, img, pet):
        self.img = img
        self.pet = pet
        self.mode = None
        self.box = None
        self.grab_off = None
        self.corner = None

        self.win = tk.Toplevel(pet.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            ox = int(pet.root.winfo_vrootx())
            oy = int(pet.root.winfo_vrooty())
            vw = int(pet.root.winfo_vrootwidth()) or img.width
            vh = int(pet.root.winfo_vrootheight()) or img.height
        except Exception:
            ox, oy, vw, vh = 0, 0, img.width, img.height
        self.win.geometry("%dx%d+%d+%d" % (vw, vh, ox, oy))
        self.vw, self.vh = vw, vh

        # 底层：42% 亮度整屏
        dimmed = img.resize((vw, vh))
        self.dim = dimmed.point(lambda p: int(p * 0.42))
        self.dim_tk = ImageTk.PhotoImage(self.dim)
        # 原亮度整屏（框内贴用）
        self.full = dimmed
        self.full_tk = ImageTk.PhotoImage(self.full)

        self.cv = tk.Canvas(self.win, width=vw, height=vh, highlightthickness=0,
                            bd=0, bg="black", cursor="crosshair")
        self.cv.pack(fill="both", expand=True)
        self.cv.create_image(0, 0, anchor="nw", image=self.dim_tk, tags="dim")
        self.patch_id = self.cv.create_image(0, 0, anchor="nw", state="hidden", tags="patch")
        self.frame_id = self.cv.create_rectangle(0, 0, 0, 0, outline=BRAND, width=1.6,
                                                 state="hidden", tags="frame")

        self.cv.bind("<ButtonPress-1>", self.down)
        self.cv.bind("<B1-Motion>", self.move)
        self.cv.bind("<ButtonRelease-1>", self.up)
        self.cv.bind("<Double-Button-1>", self.confirm)
        self.win.bind("<Escape>", lambda e: self.close())
        self.win.focus_force()

    def hit(self, x, y):
        if not self.box:
            return None
        x1, y1, x2, y2 = self.box
        e = self.EDGE
        for name, cx, cy in (("tl", x1, y1), ("tr", x2, y1), ("bl", x1, y2), ("br", x2, y2)):
            if abs(x - cx) <= e and abs(y - cy) <= e:
                return ("resize", name)
        if x1 + e < x < x2 - e and y1 + e < y < y2 - e:
            return ("inside", None)
        near_l = abs(x - x1) <= e and y1 - e < y < y2 + e
        near_r = abs(x - x2) <= e and y1 - e < y < y2 + e
        near_t = abs(y - y1) <= e and x1 - e < x < x2 + e
        near_b = abs(y - y2) <= e and x1 - e < x < x2 + e
        if near_l or near_r or near_t or near_b:
            return ("resize", "edge")
        return None

    def down(self, e):
        h = self.hit(e.x, e.y)
        if h and h[0] == "inside":
            self.mode = "move"
            self.grab_off = (e.x - self.box[0], e.y - self.box[1])
        elif h and h[0] == "resize":
            self.mode = "resize"
            self.corner = h[1]
            self.grab_off = (e.x, e.y, list(self.box))
        else:
            self.mode = "new"
            self.box = [e.x, e.y, e.x, e.y]
            self.paint()

    def move(self, e):
        if self.mode == "new":
            x1, y1 = self.box[0], self.box[1]
            self.box = [min(x1, e.x), min(y1, e.y), max(x1, e.x), max(y1, e.y)]
            self.paint()
        elif self.mode == "move" and self.box:
            w = self.box[2] - self.box[0]
            h = self.box[3] - self.box[1]
            nx = max(0, min(self.vw - w, e.x - self.grab_off[0]))
            ny = max(0, min(self.vh - h, e.y - self.grab_off[1]))
            self.box = [nx, ny, nx + w, ny + h]
            self.paint()
        elif self.mode == "resize" and self.box:
            x0, y0, ob = self.grab_off
            dx, dy = e.x - x0, e.y - y0
            b = list(ob)
            c = self.corner
            if c in ("tl", "edge"):
                b[0] = min(ob[2] - 8, ob[0] + dx)
                b[1] = min(ob[3] - 8, ob[1] + dy)
            if c in ("br", "edge"):
                b[2] = max(ob[0] + 8, ob[2] + dx)
                b[3] = max(ob[1] + 8, ob[3] + dy)
            if c == "tr":
                b[2] = max(ob[0] + 8, ob[2] + dx)
                b[1] = min(ob[3] - 8, ob[1] + dy)
            if c == "bl":
                b[0] = min(ob[2] - 8, ob[0] + dx)
                b[3] = max(ob[1] + 8, ob[3] + dy)
            self.box = b
            self.paint()

    def up(self, e):
        self.mode = None
        if self.box and (self.box[2] - self.box[0]) < 6:
            self.box = None
            self.paint()

    def paint(self):
        if not self.box:
            self.cv.itemconfigure(self.patch_id, state="hidden")
            self.cv.itemconfigure(self.frame_id, state="hidden")
            self.cv.delete("sz")
            return
        x1, y1, x2, y2 = [int(v) for v in self.box]
        w, h = max(1, x2 - x1), max(1, y2 - y1)
        try:
            piece = self.full.crop((x1, y1, x2, y2))
            self.patch_tk = ImageTk.PhotoImage(piece)
            self.cv.itemconfigure(self.patch_id, image=self.patch_tk, state="normal")
            self.cv.coords(self.patch_id, x1, y1)
        except Exception:
            pass
        self.cv.itemconfigure(self.frame_id, state="normal")
        self.cv.coords(self.frame_id, x1, y1, x2, y2)
        self.cv.tag_raise("frame")

        self.cv.delete("sz")
        self.cv.create_rectangle(x1 + 3, y1 + 3, x1 + 96, y1 + 27,
                                 fill="#FFFFFF", outline="", tags="sz")
        self.cv.create_text(x1 + 50, y1 + 15, text="%d × %d" % (w, h),
                            fill="#111111", tags="sz",
                            font=("Microsoft YaHei UI", 10, "bold"))
        self.cv.tag_raise("sz")

    def confirm(self, e):
        if not self.box:
            return
        h = self.hit(e.x, e.y)
        if not h or h[0] != "inside":
            return
        x1, y1, x2, y2 = [int(v) for v in self.box]
        sx = self.img.width / float(self.vw)
        sy = self.img.height / float(self.vh)
        bx = (int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy))
        if bx[2] - bx[0] < 2 or bx[3] - bx[1] < 2:
            return
        try:
            cropped = self.img.crop(bx)
        except Exception:
            self.close()
            return
        ensure_dir()
        path = os.path.join(OUT_DIR, "pet-%s.png" % time.strftime("%Y%m%d-%H%M%S"))
        try:
            cropped.save(path, "PNG")
            with open(LATEST, "w", encoding="utf-8") as f:
                f.write(path)
        except Exception:
            pass
        self.close()

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass
        self.pet.shot = None


# ============================================================ 入口
def already_running():
    lock = os.path.join(os.environ.get("TEMP", "."), "dsh-pet.lock")
    if not os.path.exists(lock):
        return None, lock
    try:
        with open(lock, "r") as f:
            old = int(f.read().strip() or 0)
    except Exception:
        return None, lock
    if old <= 0 or old == os.getpid():
        return None, lock
    try:
        import subprocess
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"ProcessId=%d\").CommandLine" % old],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            timeout=6, creationflags=0x08000000,
        ).stdout or ""
        if "dsh-pet.py" in out:
            return old, lock
    except Exception:
        pass
    return None, lock


if __name__ == "__main__":
    running, lock = already_running()
    if running:
        sys.exit(0)
    try:
        with open(lock, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    Pet().run()
