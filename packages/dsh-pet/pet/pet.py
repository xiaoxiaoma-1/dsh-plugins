# -*- coding: utf-8 -*-
"""
dsh-pet —— Grok Bot 桌面宠物（dsh-pet 插件的桌面层，由插件 spawn）

形象：1:1 复刻 Grok Bot
  · 完美正圆（不是圆角方）
  · 眼睛是两个「挖出来的白色洞」（mask holes），无瞳孔、无描边
  · 小尺寸下角度归零（26° 倾角只在大尺寸成立，56px 上会变歪眼）
  · 静止时球体完全不动，全部活力来自「视线漂移 + 眨眼」
  · 视线跟随鼠标：靠两个眼洞整体偏移，不是瞳孔移动

交互：
  · 拖 = 移动位置
  · 点 = 弹出/收起菜单（菜单里看对话进度、截图、退出）
"""

import os
import sys
import json
import math
import time
import threading
import urllib.request
import urllib.error
import tkinter as tk

# 贾维斯的耳朵和嘴（独立模块：录音 / 转写 / 合成 / 播报 / 打断）
try:
    VJ = None          # 2026-11-09 贾维斯 AI 已拆除，不再加载耳朵和嘴
except Exception:
    VJ = None

try:
    from PIL import Image, ImageDraw, ImageTk, ImageGrab
except Exception:
    sys.exit(1)


def enable_dpi_awareness():
    """让 Tk 按物理像素工作。

    不开：系统 DPI 150% 时，Tk 画的 56px 球实际只渲染 37px，
    菜单 306px 只显示 197px，圆角半径、「角落弧形」全部跟着缩，
    看上去就是「粗糙、发虚、圆角对不上」。必须在 Tk() 之前调用。
    """
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # per-monitor
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


enable_dpi_awareness()

# ---------------- 尺寸与配色 ----------------
BALL = 56                       # 球直径
PAD = 10                        # 留白（给轮廓光、徽标）
CANVAS = BALL + PAD * 2         # 76
MARGIN = 14
KEY = "#010203"                 # 抠色键（球体用）
KEY2 = "#040506"                # 抠色键（菜单/气泡用，让圆角外真的透明，不是黑边）

C_CORE = "#232329"              # 球心（受光面）
C_EDGE = "#0C0C10"              # 球缘
C_RIM = "#3A3A44"               # 轮廓细边（保证深色桌面也看得见）
EYE = "#F7F3EA"                 # 眼洞

# 眼睛颜色就是贾维斯的状态灯：待机白、在听金、在想蓝、在说绿
VSTATE_COLOR = {
    "off": EYE,
    "idle": EYE,
    "listening": "#FFE39A",
    "thinking": "#8FC7FF",
    "speaking": "#9BF0B0",
}

BG = "#17171B"                  # 菜单底
BG_CARD = "#202027"             # 卡片底
LINE = "#2E2E36"                # 分隔线
TXT = "#ECECEE"                 # 主文字
SUB = "#9A9AA2"                 # 次要文字
GOLD = "#D9A94A"
GREEN = "#78DC8C"
RED = "#E2665E"

FONT = "Microsoft YaHei UI"
MENU_W = 306
MENU_GAP = 8                    # 菜单和球之间留的空隙（键色，透明）

OUT_DIR = r"E:\desktop\shots"

# DSH 会话存档（标题兜底要从这里读：session/title 事件只在标题变化时发一次，
# 插件启动时已有会话不会再发，所以菜单里会一直是空标题）
SESS_ROOT = r"E:\DSH-data\.dsh\sessions"


def lookup_session_title(sid):
    """从会话存档里翻出这个会话最后的标题。读一次几百毫秒，别在主线程调。"""
    if not sid:
        return ""
    try:
        import glob
        import io
        import zstandard
    except Exception:
        return ""
    title = ""
    try:
        pats = os.path.join(SESS_ROOT, "*", sid, "session.v4.jsonl.zstd")
        files = glob.glob(pats)
        if not files:
            return ""
        with open(files[0], "rb") as f:
            dctx = zstandard.ZstdDecompressor()
            with dctx.stream_reader(f) as r:
                buf = io.BufferedReader(r)
                n = 0
                while n < 8000:
                    line = buf.readline()
                    if not line:
                        break
                    n += 1
                    if b"session/title" not in line:
                        continue
                    try:
                        j = json.loads(line.decode("utf-8", "ignore"))
                    except Exception:
                        continue
                    if j.get("type") != "session/title":
                        continue
                    t = (j.get("data") or {}).get("title") or ""
                    if isinstance(t, str) and t.strip():
                        title = t.strip()
    except Exception:
        pass
    return title


def ensure_dir():
    os.makedirs(OUT_DIR, exist_ok=True)


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


def fmt_ms(ms):
    s = int(ms / 1000)
    if s < 60:
        return "%d秒" % s
    m = s // 60
    if m < 60:
        return "%d分%d秒" % (m, s % 60)
    return "%d小时%d分" % (m // 60, m % 60)


def mmss(sec):
    sec = max(0, int(float(sec or 0)))
    return "%02d:%02d" % (sec // 60, sec % 60)


def round_window(win, w, h, r=18):
    """把窗口外形直接裁成圆角。

    只靠 -transparentcolor 抠键色在 Toplevel 上不可靠（实测四角还是直角 + 一圈键色黑边）。
    SetWindowRgn 改的是窗口区域本身，圆角是确定的，不存在黑边。

    ★ 必须声明 argtypes/restype：64 位进程里 HANDLE 是 64 位，
      不声明会被截成 32 位无效句柄 —— 表现是「整个窗口消失」。
    """
    try:
        import ctypes
        from ctypes import wintypes
        gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        user = ctypes.WinDLL("user32", use_last_error=True)
        gdi.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
        gdi.CreateRoundRectRgn.restype = wintypes.HANDLE
        user.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.BOOL]
        user.SetWindowRgn.restype = ctypes.c_int
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND

        # Tk 的 Toplevel 在 Windows 上 winfo_id() 就是真实顶层 HWND；
        # wm_frame() 对 overrideredirect 窗口经常拿不到，GetParent 又会爬错。
        hwnd = win.winfo_id()
        if not hwnd:
            return False
        hrgn = gdi.CreateRoundRectRgn(0, 0, int(w) + 1, int(h) + 1, int(r) * 2, int(r) * 2)
        if not hrgn:
            return False
        return bool(user.SetWindowRgn(hwnd, hrgn, True))
    except Exception:
        return False


# ============================================================ 球体图像
def make_ball(size, ball=BALL):
    """正圆 + 径向渐变 + 1px 轮廓。

    两个必须守的点（都踩过）：
      1. 圆只占中间 `ball` 大小，不是铺满整张画布 —— 否则球直径会等于画布，留白失效
      2. 缩放后必须用「目标尺寸的二值 mask」再切一次边 —— LANCZOS 会在圆边产生过渡色，
         键色抠图只认精确颜色，过渡色抠不掉 → 球外面留一圈脏方框
    """
    SS = 4
    S = size * SS
    d = ball * SS
    off = (S - d) // 2
    box = [off, off, off + d - 1, off + d - 1]

    # 渐变用小块算完再放大（省 CPU）
    G = 56
    small = Image.new("L", (G, G), 0)
    px = small.load()
    cx = cy = (G - 1) / 2.0
    maxd = math.hypot(cx, cy)
    for y in range(G):
        for x in range(G):
            dd = math.hypot(x - cx, y - cy) / maxd
            dd = min(1.0, dd)
            px[x, y] = int(255 * (1.0 - dd ** 1.4))
    grad = small.resize((S, S), Image.LANCZOS)

    core = Image.new("RGB", (S, S), _h(C_CORE))
    edge = Image.new("RGB", (S, S), _h(C_EDGE))
    body = Image.composite(core, edge, grad)

    # 正圆遮罩（不是圆角矩形）
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    mask = mask.point(lambda p: 255 if p > 128 else 0)

    out = Image.new("RGB", (S, S), _h(KEY))
    out.paste(body, (0, 0), mask)

    # 轮廓细边：只描在圆的外圈
    ring = Image.new("L", (S, S), 0)
    rd = ImageDraw.Draw(ring)
    rd.ellipse(box, outline=255, width=max(2, SS))
    ring = ring.point(lambda p: 255 if p > 100 else 0)
    rim = Image.new("RGB", (S, S), _h(C_RIM))
    out.paste(rim, (0, 0), ring)

    # ★ LANCZOS 求平滑 → 目标尺寸二值 mask 切边 → 边缘一个过渡色都不留
    smoothed = out.resize((size, size), Image.LANCZOS)
    cut = mask.resize((size, size), Image.BOX).point(lambda p: 255 if p > 127 else 0)
    final = Image.new("RGB", (size, size), _h(KEY))
    final.paste(smoothed, (0, 0), cut)
    return final


# ============================================================ 位置记忆
POS_FILE = os.path.join(os.environ.get("TEMP", "."), "dsh-pet-pos.json")


def load_pos():
    try:
        with open(POS_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return int(d["x"]), int(d["y"])
    except Exception:
        return None


def save_pos(x, y):
    try:
        with open(POS_FILE, "w", encoding="utf-8") as f:
            json.dump({"x": int(x), "y": int(y)}, f)
    except Exception:
        pass


# ============================================================ 主窗口
class Pet:
    def __init__(self):
        self.port = None
        self.data = {"running": [], "runningCount": 0, "done": []}
        self.pod = {}
        self.menu = None
        self.shot = None
        self._drag = None
        self._moved = False
        self._fail = 0
        self.blink = False
        self.eye_dx = 0.0
        self.eye_dy = 0.0
        self._poking = False
        self._scale = 1.0
        self._menu_sig = None
        self._title_cache = {}      # ★ 少了这一行，轮询里第一次访问就抛 AttributeError，标题永远空
        self._rows = []
        self._pod_rows = []
        self.toast = None
        self._last_done_at = 0

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-transparentcolor", KEY)
        except Exception:
            pass
        self.root.configure(bg=KEY)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # 恢复上次的位置；恢复不了（文件丢了/跑到屏幕外）才用默认的右下角
        saved = load_pos()
        if saved and self.pos_ok(saved[0], saved[1]):
            self.x, self.y = saved
        else:
            self.x = sw - CANVAS - MARGIN
            self.y = sh - CANVAS - MARGIN - 90
        self.root.geometry("%dx%d+%d+%d" % (CANVAS, CANVAS, self.x, self.y))

        self.cv = tk.Canvas(self.root, width=CANVAS, height=CANVAS, bg=KEY,
                            highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)

        # ★ 只绑 Toplevel，不绑 Canvas。
        #   tkinter 的事件沿 bindtags 传播：Canvas 实例 → Canvas 类 → Toplevel → all。
        #   两边都绑 → 一次点击跑两遍 → toggle_menu 开完立刻被第二次关掉，表现为「点不开」。
        self.root.bind("<ButtonPress-1>", self.on_press)
        self.root.bind("<B1-Motion>", self.on_drag)
        self.root.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Button-3>", self.on_rclick)

        self.build()

        threading.Thread(target=self.poll_loop, daemon=True).start()
        self.root.after(60, self.tick_eye)
        self.root.after(150, self.tick_blink)
        self.root.after(200, self.tick_menu)

        # 贾维斯：默认开麦。喊「贾维斯」就醒，或者点一下球也能把它叫起来。
        self.vstate = "off"
        self.voice = None
        self._bubble = None
        self._bubble_after = None
        # 2026-11-09 贾维斯 AI 已拆除：不再起麦克风、不再接大模型

    # -------- 构建
    # ★ 球和菜单共用一个 Tk 根窗口：只有根窗口的 -transparentcolor 才真的能抠掉键色，
    #   Toplevel 上抠不掉、也裁不了圆角（实测 12 轮）。窗口按需向上长高，球永远贴底。
    def ball_layer(self):
        """CANVAS×CANVAS 的球图（不含眼睛），按 scale 缓存"""
        key = round(self._scale, 3)
        hit = self._ball_cache.get(key)
        if hit is None:
            n = max(10, int(round(BALL * self._scale)))
            hit = make_ball(CANVAS, n)
            self._ball_cache[key] = hit
        return hit.copy()

    def pos_ok(self, x, y):
        """位置是否落在某块屏幕里（多屏用虚拟桌面边界判断，负坐标也算合法）"""
        try:
            vx = int(self.root.winfo_vrootx())
            vy = int(self.root.winfo_vrooty())
            vw = int(self.root.winfo_vrootwidth())
            vh = int(self.root.winfo_vrootheight())
            return (vx - CANVAS < x < vx + vw) and (vy - CANVAS < y < vy + vh)
        except Exception:
            return False

    def build(self):
        self._ball_cache = {}
        self.win_w = CANVAS
        self.win_h = CANVAS
        self.off = 0
        self.ball_x = 0
        self.menu_h = 0
        self._shell = Image.new("RGB", (CANVAS, CANVAS), _h(KEY))
        self._tkimg = ImageTk.PhotoImage(self._shell)
        self._i_ball = self.cv.create_image(0, 0, anchor="nw", image=self._tkimg)
        self.render_face()

    def resize_shell(self, menu_h=0):
        """菜单开/关时改窗口尺寸；球在屏幕上的位置不变，且始终和菜单水平居中"""
        W = max(CANVAS, MENU_W) if menu_h else CANVAS
        H = CANVAS + (menu_h + MENU_GAP if menu_h else 0)
        self.win_w, self.win_h = W, H
        self.off = H - CANVAS
        self.ball_x = (W - CANVAS) // 2      # ★ 球和菜单水平居中
        self.menu_h = menu_h
        self._shell = Image.new("RGB", (W, H), _h(KEY))
        self._tkimg = ImageTk.PhotoImage(self._shell)
        self.cv.configure(width=W, height=H)
        self.cv.itemconfigure(self._i_ball, image=self._tkimg)
        self.cv.coords(self._i_ball, 0, 0)
        self.cv.delete("menu")
        # 窗口位置由「球在屏幕上的位置 - 球在窗口内的偏移」反推，球不会跳
        wx = self.x - self.ball_x
        wy = self.y - self.off
        self.root.geometry("%dx%d+%d+%d" % (W, H, int(wx), int(wy)))
        self.render_face()

    def render_face(self):
        """整窗重绘：键色底 + 球（贴底）+ 两个眼洞"""
        W, H = self.win_w, self.win_h
        img = Image.new("RGB", (W, H), _h(KEY))
        ball = self.ball_layer()
        d = ImageDraw.Draw(ball)
        cx = cy = CANVAS / 2.0
        s = self._scale
        ew, eh = 8.4 * s, (2.2 if self.blink else 12.6) * s
        gap = 7.0 * s
        dx, dy = self.eye_dx * s, self.eye_dy * s
        ey0 = cy - eh / 2.0 + dy - 0.5 * s
        eye_col = _h(VSTATE_COLOR.get(getattr(self, "vstate", "off"), EYE))
        d.ellipse([cx - gap / 2 - ew + dx, ey0, cx - gap / 2 + dx, ey0 + eh], fill=eye_col)
        d.ellipse([cx + gap / 2 + dx, ey0, cx + gap / 2 + ew + dx, ey0 + eh], fill=eye_col)
        img.paste(ball, (self.ball_x, self.off))
        self._shell = img
        self._tkimg.paste(img)

    # -------- 视线跟随（33ms）与眨眼
    def tick_eye(self):
        try:
            mx, my = self.root.winfo_pointerxy()
            cx = self.x + CANVAS / 2.0
            cy = self.y + CANVAS / 2.0
            ddx, ddy = mx - cx, my - cy
            length = math.hypot(ddx, ddy)
            if length < 0.001:
                self.eye_dx = self.eye_dy = 0.0
            else:
                k = min(1.0, length / 160.0) * 2.4
                self.eye_dx = ddx / length * k
                self.eye_dy = ddy / length * k
            self.render_face()
        except Exception:
            pass
        self.root.after(33, self.tick_eye)

    def tick_blink(self):
        self.blink = True
        self.render_face()
        self.root.after(110, self._unblink)
        self.root.after(3000 + int(time.time() * 7) % 3200, self.tick_blink)

    def _unblink(self):
        self.blink = False
        self.render_face()

    # -------- 贾维斯：耳朵和嘴
    def start_voice(self):
        if VJ is None:
            self.show_bubble("注意", "voice.py 没找到，语音起不来")
            return
        try:
            v = VJ.Voice(
                get_port=lambda: self.port,
                on_text=self._v_text,
                on_reply=self._v_reply,
                on_state=self._v_state,
                on_warn=self._v_warn,
            )
            self.voice = v
            if v.start():
                self.vstate = "idle"
                self.render_face()
        except Exception as e:
            self.show_bubble("注意", "语音起不来：%s" % e)

    # 下面四个回调都在音频线程里，必须转回主线程再碰界面
    def _v_state(self, s):
        try:
            self.root.after(0, lambda: self._apply_vstate(s))
        except Exception:
            pass

    def _apply_vstate(self, s):
        self.vstate = s
        self.render_face()

    def _v_text(self, t):
        try:
            self.root.after(0, lambda: self.show_bubble("你", t, 4200))
        except Exception:
            pass

    def _v_reply(self, t):
        try:
            self.root.after(0, lambda: self.show_bubble("贾维斯", t, 7000))
        except Exception:
            pass

    def _v_warn(self, t):
        try:
            self.root.after(0, lambda: self.show_bubble("注意", t, 9000))
        except Exception:
            pass

    def wake_jarvis(self):
        """点球 = 叫醒（不用非喊名字）"""
        if not self.voice:
            return False
        if self.vstate in ("off",):
            return False
        try:
            self.voice.wake()
            self.show_bubble("贾维斯", "在呢，有什么吩咐？", 3500)
            return True
        except Exception:
            return False

    # -------- 对话气泡
    def show_bubble(self, who, text, ms=6000):
        try:
            if self._bubble is not None and self._bubble.winfo_exists():
                self._bubble.destroy()
        except Exception:
            pass
        W, H = 340, 104
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        try:
            t.attributes("-transparentcolor", KEY)
        except Exception:
            pass
        t.configure(bg=KEY)
        tc = tk.Canvas(t, width=W, height=H, bg=KEY, highlightthickness=0, bd=0)
        tc.pack()

        img = Image.new("RGB", (W, H), _h(KEY))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, W - 1, H - 1], radius=16, fill=_h(BG),
                            outline=_h(_mix(GOLD, BG, 0.55)))
        tkimg = ImageTk.PhotoImage(img)
        c_img = tc.create_image(0, 0, anchor="nw", image=tkimg)
        self._bubble_img = tkimg

        tc.create_text(18, 22, text=who, anchor="w",
                       fill=GOLD if who == "贾维斯" else SUB, font=(FONT, 11, "bold"))
        body = (text or "").strip()
        lines = []
        cur = ""
        for ch in body:
            cur += ch
            if len(cur) >= 19:
                lines.append(cur)
                cur = ""
            if len(lines) >= 3:
                break
        if cur and len(lines) < 3:
            lines.append(cur)
        if not lines:
            lines = ["…"]
        y = 44
        for ln in lines:
            tc.create_text(18, y, text=ln, anchor="w", fill=TXT, font=(FONT, 11))
            y += 20

        self._bubble = t
        t.update_idletasks()
        t.geometry("%dx%d" % (W, H))
        round_window(t, W, H, 16)
        self.place_bubble()
        t.bind("<Button-1>", lambda e: self.close_bubble())
        try:
            if self._bubble_after:
                self.root.after_cancel(self._bubble_after)
        except Exception:
            pass
        self._bubble_after = self.root.after(ms, self.close_bubble)

    def place_bubble(self):
        if not self._bubble or not self._bubble.winfo_exists():
            return
        try:
            W = self._bubble.winfo_width()
            if W <= 1:
                W = 340
            H = self._bubble.winfo_height()
            if H <= 1:
                H = 104
            vx, vy = int(self.root.winfo_vrootx()), int(self.root.winfo_vrooty())
            vw, vh = int(self.root.winfo_vrootwidth()), int(self.root.winfo_vrootheight())
            x = max(vx + 8, min(self.x + CANVAS - W, vx + vw - W - 8))
            y = self.y - H - 10
            if y < vy + 8:
                y = vy + 8
            self._bubble.geometry("%dx%d+%d+%d" % (int(W), int(H), int(x), int(y)))
        except Exception:
            pass

    def close_bubble(self):
        try:
            if self._bubble is not None:
                self._bubble.destroy()
        except Exception:
            pass
        self._bubble = None

    # -------- 拖动 / 点击
    def on_press(self, e):
        # 菜单区域里按下：不算拖球
        self._in_menu = bool(self.menu_h) and e.y < self.off
        self._drag = (e.x_root - self.x, e.y_root - self.y)
        self._moved = False

    def on_drag(self, e):
        if not self._drag or getattr(self, "_in_menu", False):
            return
        nx = e.x_root - self._drag[0]
        ny = e.y_root - self._drag[1]
        if abs(nx - self.x) > 3 or abs(ny - self.y) > 3:
            self._moved = True
        self.x, self.y = nx, ny
        self.root.geometry("+%d+%d" % (int(nx - self.ball_x), int(ny - self.off)))

    def on_release(self, e):
        was = self._moved
        in_menu = getattr(self, "_in_menu", False)
        self._drag = None
        self._in_menu = False
        if was:
            save_pos(self.x, self.y)      # 松手就记住位置，下次启动回到这里
            return "break"
        if in_menu:
            # 点在菜单空白处 → 收起（按钮自己会 return break，不会走到这）
            self.close_menu()
            return "break"
        self.poke()
        self.toggle_menu()
        return "break"

    def on_rclick(self, e):
        self.toggle_menu()
        return "break"

    def poke(self):
        """点一下弹一下，给个手感回执"""
        if self._poking:
            return
        self._poking = True
        seq = [0.86, 1.09, 0.94, 1.03, 1.0]

        def step(i):
            if i >= len(seq):
                self._poking = False
                self._scale = 1.0
                self.render_face()
                return
            self._scale = seq[i]
            self.render_face()
            self.root.after(38, lambda: step(i + 1))

        step(0)

    # -------- 状态轮询
    def poll_loop(self):
        while True:
            try:
                if self.port is None:
                    self.port = self.find_port()
                if self.port:
                    try:
                        req = urllib.request.Request(
                            "http://127.0.0.1:%d/pet/status" % self.port)
                        with urllib.request.urlopen(req, timeout=2) as r:
                            j = json.loads(r.read().decode("utf-8"))
                    except urllib.error.HTTPError as he:
                        # 404 = 插件这条路由没注册，但 DSH 活着 → 端口是对的，别丢
                        if he.code == 404:
                            j = None
                        else:
                            raise
                    if j is not None:
                        if j.get("ok"):
                            self.data = j
                            self._fail = 0
                            # 宿主没给标题的就自己翻存档补上（缓存 60 秒）
                            now = time.time()
                            for item in (j.get("running") or []):
                                if (item.get("title") or "").strip():
                                    continue
                                sid = item.get("id") or ""
                                hit = self._title_cache.get(sid)
                                if hit and now - hit[1] < 60:
                                    if hit[0]:
                                        item["title"] = hit[0]
                                    continue
                                t = lookup_session_title(sid)
                                self._title_cache[sid] = (t, now)
                                if t:
                                    item["title"] = t
                        else:
                            self.port = None
                            self._fail += 1
                    # 播客状态（有音频时菜单里出播放控制）
                    try:
                        req2 = urllib.request.Request(
                            "http://127.0.0.1:%d/podcast/state" % self.port)
                        with urllib.request.urlopen(req2, timeout=1.5) as r2:
                            self.pod = json.loads(r2.read().decode("utf-8"))
                    except Exception:
                        pass
                else:
                    self.data = {"running": [], "runningCount": 0, "done": []}
                    self._fail += 1
            except Exception:
                self.port = None
                self._fail += 1
            delay = 3 if not self._fail else min(30, 3 * (2 ** min(self._fail - 1, 4)))
            time.sleep(delay)

    def find_port(self):
        ports = []
        try:
            import subprocess
            out = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command",
                 "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
                 "Where-Object { $_.LocalPort -ge 20000 -and $_.LocalPort -le 66000 } | "
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
            # 先认 /pet/status（桌宠自己的），再退一步认 /call/health（dsh-call 的）。
            # 只要有一个通，这个端口就是 DSH —— 某个插件没注册不该让整只桌宠失联。
            for probe in ("/pet/status", "/call/health"):
                try:
                    req = urllib.request.Request("http://127.0.0.1:%d%s" % (p, probe))
                    with urllib.request.urlopen(req, timeout=0.35) as r:
                        if r.status == 200:
                            json.loads(r.read().decode("utf-8"))
                            return p
                except Exception:
                    continue
        return None

    def tick_menu(self):
        """菜单开着：数据变了才重画；数字/播放进度就地刷新"""
        self.check_done()
        if self.menu_h:
            sig = self.menu_signature()
            if sig != self._menu_sig:
                self._menu_sig = sig
                self.cv.delete("menu")
                self.draw_menu()
            else:
                self.update_times()
                self.update_pod_time()
        self.root.after(400, self.tick_menu)

    def update_pod_time(self):
        pod = self.pod or {}
        for t in self._pod_rows:
            try:
                t.configure(text="%s / %s" % (mmss(pod.get("pos")), mmss(pod.get("dur"))))
            except Exception:
                pass

    # -------- 「任务完成」主动弹一下
    def check_done(self):
        done = self.data.get("done") or []
        if not done:
            return
        top = done[0]
        at = top.get("at") or 0
        if not at:
            return
        if self._last_done_at == 0:
            self._last_done_at = at          # 首次只记基线，不弹（否则一启动就弹一堆历史）
            return
        if at > self._last_done_at:
            self._last_done_at = at
            self.show_toast(top.get("title"))
            self.poke()

    def show_toast(self, title):
        try:
            if self.toast and self.toast.winfo_exists():
                self.toast.destroy()
        except Exception:
            pass
        W, H = 322, 96
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        try:
            t.attributes("-transparentcolor", KEY)
        except Exception:
            pass
        t.configure(bg=KEY)
        tc = tk.Canvas(t, width=W, height=H, bg=KEY, highlightthickness=0, bd=0)
        tc.pack()

        img = Image.new("RGB", (W, H), _h(KEY))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, W - 1, H - 1], radius=16, fill=_h(BG),
                            outline=_h(_mix(GOLD, BG, 0.55)))
        tkimg = ImageTk.PhotoImage(img)
        c_img = tc.create_image(0, 0, anchor="nw", image=tkimg)
        self._toast_img = tkimg        # ★ 不留引用会被 GC，图片消失 → 整窗被抠成透明
        tc.itemconfigure(c_img, image=tkimg)

        tc.create_oval(17, 20, 27, 30, fill=GREEN, outline="")
        tc.create_text(37, 25, text="主人，任务完成了", anchor="w", fill=TXT, font=(FONT, 12, "bold"))
        tt = (title or "").strip() or "有一项任务"
        if len(tt) > 12:
            tt = tt[:12] + "…"
        tc.create_text(18, 49, text="「%s」跑完了" % tt, anchor="w",
                       fill=_mix(GOLD, TXT, 0.3), font=(FONT, 11))
        tc.create_text(18, 73, text="回 DSH 看看 →", anchor="w", fill=SUB, font=(FONT, 10))

        self.toast = t
        t.update_idletasks()
        t.geometry("%dx%d" % (W, H))
        round_window(t, W, H, 16)
        self.place_toast()
        t.bind("<Button-1>", lambda e: self.close_toast())
        t.after(7000, self.close_toast)

    def place_toast(self):
        if not self.toast or not self.toast.winfo_exists():
            return
        try:
            # ★ winfo_width() 未映射时返回 1，而 `1 or 306` 还是 1 → 窗口被压成 1px。
            #   必须用 <= 1 判断，不能靠 or。
            W = self.toast.winfo_width()
            if W <= 1:
                W = 306
            H = self.toast.winfo_height()
            if H <= 1:
                H = 96
            vx, vy = int(self.root.winfo_vrootx()), int(self.root.winfo_vrooty())
            vw, vh = int(self.root.winfo_vrootwidth()), int(self.root.winfo_vrootheight())
            x = max(vx + 8, min(self.x + CANVAS - W, vx + vw - W - 8))
            y = self.y - H - 10
            if y < vy + 8:
                y = vy + 8
            self.toast.geometry("%dx%d+%d+%d" % (int(W), int(H), int(x), int(y)))
        except Exception:
            pass

    def close_toast(self):
        if self.toast:
            try:
                self.toast.destroy()
            except Exception:
                pass
            self.toast = None

    def menu_signature(self):
        run = self.data.get("running") or []
        pod = self.pod or {}
        return (
            self.port,
            tuple((r.get("id") or "", r.get("title") or "") for r in run[:4]),
            bool(pod.get("hasSrc")),
            bool(pod.get("playing")),
            (pod.get("title") or "")[:24],
        )

    def update_times(self):
        run = self.data.get("running") or []
        for item in self._rows:
            try:
                if item[0] == "time" and item[1] < len(run):
                    item[2].configure(text=fmt_ms(run[item[1]].get("ms", 0)))
            except Exception:
                pass

    # -------- 菜单（画在球同一个根窗口的上半部分）
    def toggle_menu(self):
        if self.menu_h:
            self.close_menu()
        else:
            self.open_menu()

    def open_menu(self):
        if self.menu_h:
            return
        self._menu_sig = None
        self.resize_shell(self.compute_menu_h())
        self.draw_menu()

    def close_menu(self):
        if not self.menu_h:
            return
        self.resize_shell(0)

    def compute_menu_h(self):
        run = self.data.get("running") or []
        has_pod = bool((self.pod or {}).get("hasSrc"))
        pad = 13
        h = pad + 30 + len(run[:4]) * 40
        if has_pod:
            h += 8 + 56
        h += 12 + 40 + pad
        return h

    def draw_menu(self):
        if not self.menu_h:
            return
        run = self.data.get("running") or []
        pod = self.pod or {}
        has_pod = bool(pod.get("hasSrc"))
        self._rows = []

        pad = 13
        run_show = run[:4]
        h = self.menu_h

        c = self.cv
        existing = set(c.find_all())
        self._card_imgs = []       # ★ 每张卡片的图都要留引用，否则被 GC → 背景消失
        self._btn_imgs = []
        self._pod_rows = []

        # 菜单底板：圆角外面是键色，根窗口抠色后就是真透明，所以四角是真的圆
        bgimg = self.round_rect(MENU_W, h, 18, BG, KEY)
        self._bg_tk = ImageTk.PhotoImage(bgimg)
        c.create_image(0, 0, anchor="nw", image=self._bg_tk)
        c.create_line(pad + 2, 0.5, MENU_W - pad - 2, 0.5, fill=_mix(GOLD, BG, 0.74))

        y = pad + 2
        n = int(self.data.get("runningCount") or 0)
        if self.port is None:
            head, head_color, dot = "没连上 DSH", RED, RED
        elif n == 0:
            head, head_color, dot = "闲着，没活儿", SUB, _mix(SUB, BG, 0.45)
        elif n == 1:
            head, head_color, dot = "你派发的任务开始干活了", TXT, GOLD
        else:
            head, head_color, dot = "%d 个任务正在干活" % n, TXT, GOLD
        c.create_oval(15, y + 9, 21, y + 15, fill=dot, outline="")
        c.create_text(28, y + 12, text=head, anchor="w", fill=head_color, font=(FONT, 12, "bold"))
        y += 30

        for i, r in enumerate(run_show):
            card = self.round_rect(MENU_W - pad * 2, 34, 9, BG_CARD)
            card_tk = ImageTk.PhotoImage(card)
            self._card_imgs.append(card_tk)
            c.create_image(pad, y, anchor="nw", image=card_tk)
            c.create_rectangle(pad, y + 9, pad + 2.5, y + 25, fill=GOLD, outline="")
            title = (r.get("title") or "").strip() or "未命名任务"
            if len(title) > 16:
                title = title[:16] + "…"
            # 只显示任务名，不显示时长（用户：计一秒没意义，干脆不计时）
            c.create_text(pad + 11, y + 17, text=title, anchor="w", fill=TXT, font=(FONT, 11))
            y += 40

        # ---- 播客控制（有音频才出现）
        if has_pod:
            y += 8
            card = self.round_rect(MENU_W - pad * 2, 48, 11, BG_CARD)
            card_tk = ImageTk.PhotoImage(card)
            self._card_imgs.append(card_tk)
            c.create_image(pad, y, anchor="nw", image=card_tk, tags=("pod_row",))
            self.draw_pod_row(c, pad, y, MENU_W - pad * 2, 48)
            y += 56

        # ---- 只留一个截图（退出按钮删掉，用户不知道它是干嘛的）
        c.create_line(pad + 2, y + 5, MENU_W - pad - 2, y + 5, fill=LINE)
        y += 15
        self.mk_menu_btn(c, pad, y, MENU_W - pad * 2, 36, "截图", self.do_shot, True)

        # 本轮新画的元素统一打 menu tag，收起时一次性删掉（球是 image，不动）
        for it in c.find_all():
            if it not in existing:
                c.addtag_withtag("menu", it)

    # -------- 播客按钮
    def draw_pod_row(self, c, x, y, w, h):
        pod = self.pod or {}
        cy = y + h / 2.0
        playing = bool(pod.get("playing"))
        # 三个按钮的总宽控制在 ~90px 内，右侧留给文字，不能压上去
        self.pod_icon(c, x + 19, cy, "prev", 22)
        self.pod_icon(c, x + 49, cy, "toggle", 27, playing)
        self.pod_icon(c, x + 79, cy, "next", 22)

        title = (pod.get("title") or "").strip() or "播客"
        title = title.split("_")[0]
        if len(title) > 10:
            title = title[:10] + "…"
        tx = x + 100
        c.create_text(tx, y + 15, text=title, anchor="w", fill=TXT, font=(FONT, 10))
        t1 = c.create_text(tx, y + 33, text="%s / %s" % (mmss(pod.get("pos")), mmss(pod.get("dur"))),
                           anchor="w", fill=SUB, font=(FONT, 9))
        self._pod_rows.append(t1)

        # 末端关闭叉：鼠标移到这张卡上才出现，点一下把播客关掉
        close_id = c.create_text(x + w - 15, cy, text="×", fill=SUB, state="hidden",
                                 font=(FONT, 13), tags=("pod_close",))
        c.tag_bind("pod_row", "<Enter>",
                   lambda e: c.itemconfigure(close_id, state="normal"))
        c.tag_bind("pod_row", "<Leave>",
                   lambda e: c.itemconfigure(close_id, state="hidden"))
        c.tag_bind("pod_close", "<Enter>", lambda e: c.itemconfigure(close_id, fill=TXT))
        c.tag_bind("pod_close", "<Leave>", lambda e: c.itemconfigure(close_id, fill=SUB))
        c.tag_bind("pod_close", "<Button-1>", lambda e: self.pod_stop())

    def pod_stop(self):
        """关掉播客窗口：停音频、清状态、菜单跟着收窄"""
        self.pod = {}
        self.pod_cmd("stop")
        if self.menu_h:
            self.resize_shell(self.compute_menu_h())
            self.draw_menu()

    def pod_icon(self, c, cx, cy, kind, size, playing=False):
        tag = "pod_" + kind
        if kind == "toggle":
            c.create_oval(cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2,
                          fill=GOLD, outline="", tags=(tag,))
            if playing:
                c.create_rectangle(cx - 6, cy - 7, cx - 2, cy + 7, fill="#1A1A1A", outline="", tags=(tag,))
                c.create_rectangle(cx + 2, cy - 7, cx + 6, cy + 7, fill="#1A1A1A", outline="", tags=(tag,))
            else:
                c.create_polygon(cx - 4, cy - 8, cx - 4, cy + 8, cx + 8, cy,
                                 fill="#1A1A1A", outline="", tags=(tag,))
        else:
            c.create_oval(cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2,
                          fill=BG, outline=_mix(GOLD, BG, 0.42), tags=(tag,))
            if kind == "prev":
                c.create_polygon(cx + 5, cy - 6, cx + 5, cy + 6, cx - 3, cy, fill=TXT, outline="", tags=(tag,))
                c.create_polygon(cx - 3, cy - 6, cx - 3, cy + 6, cx - 11, cy, fill=TXT, outline="", tags=(tag,))
            else:
                c.create_polygon(cx - 5, cy - 6, cx - 5, cy + 6, cx + 3, cy, fill=TXT, outline="", tags=(tag,))
                c.create_polygon(cx + 3, cy - 6, cx + 3, cy + 6, cx + 11, cy, fill=TXT, outline="", tags=(tag,))
        cmd = {"prev": self.pod_prev, "next": self.pod_next, "toggle": self.pod_toggle}[kind]
        c.tag_bind(tag, "<Button-1>", lambda e: cmd())
        c.tag_bind(tag, "<Enter>", lambda e: c.configure(cursor="hand2"))
        c.tag_bind(tag, "<Leave>", lambda e: c.configure(cursor=""))

    def pod_toggle(self):
        self.pod_cmd("toggle")

    def pod_prev(self):
        self.pod_cmd("prev")

    def pod_next(self):
        self.pod_cmd("next")

    def pod_cmd(self, action):
        threading.Thread(target=self.pod_post, args=(action,), daemon=True).start()
        self.root.after(700, self.poll_pod_once)

    def pod_post(self, action):
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
                req = urllib.request.Request("http://127.0.0.1:%d/podcast/state" % self.port)
                with urllib.request.urlopen(req, timeout=1.5) as r:
                    self.pod = json.loads(r.read().decode("utf-8"))
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def round_rect(self, w, h, r, color, bg=None):
        """圆角图。底色默认取菜单底色 BG —— 用键色当底会在卡片四角留近黑脏角。"""
        img = Image.new("RGB", (int(w), int(h)), _h(bg or BG))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, int(w) - 1, int(h) - 1], radius=int(r), fill=_h(color))
        return img

    def mk_menu_btn(self, c, x, y, w, h, text, cmd, primary):
        bg = GOLD if primary else BG_CARD
        fg = "#1A1A1A" if primary else TXT
        img = self.round_rect(int(w), h, 9, bg)
        tkimg = ImageTk.PhotoImage(img)
        item = c.create_image(x, y, anchor="nw", image=tkimg)
        c.itemconfigure(item, tags=("btn_" + text,))
        # 保持引用，避免被 GC 掉
        if not hasattr(self, "_btn_imgs"):
            self._btn_imgs = []
        self._btn_imgs.append(tkimg)
        t = c.create_text(x + w / 2, y + h / 2, text=text, fill=fg,
                          font=(FONT, 11, "bold" if primary else "normal"),
                          tags=("btn_" + text,))
        c.tag_bind("btn_" + text, "<Button-1>", lambda e: cmd())
        c.tag_bind("btn_" + text, "<Enter>", lambda e: None)
        return t

    def place_menu(self):
        # 菜单现在和球在同一个窗口里，位置由 resize_shell 决定，这里不再需要单独摆位
        return

    # -------- 功能
    def do_shot(self):
        self.close_menu()
        self.root.withdraw()
        self.root.after(200, self._grab)

    def _grab(self):
        try:
            img = ImageGrab.grab(all_screens=True)
        except Exception:
            self.root.deiconify()
            return
        self.root.deiconify()
        self.shot = Shot(img, self)

    def quit(self):
        self.close_menu()
        try:
            self.root.destroy()
        except Exception:
            pass


# ============================================================ 截图
class Shot:
    """全屏压暗，框内还原。拖=画框，框内拖=移动，边拖=缩放，双击框内=确认，Esc=取消。"""

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

        dimmed = img.resize((vw, vh))
        self.dim = dimmed.point(lambda p: int(p * 0.42))
        self.full = dimmed
        self.dim_tk = ImageTk.PhotoImage(self.dim)
        self.full_tk = ImageTk.PhotoImage(self.full)

        self.cv = tk.Canvas(self.win, width=vw, height=vh, highlightthickness=0,
                            bd=0, bg="black", cursor="crosshair")
        self.cv.pack(fill="both", expand=True)
        self.cv.create_image(0, 0, anchor="nw", image=self.dim_tk)
        self.patch_id = self.cv.create_image(0, 0, anchor="nw", state="hidden")
        self.frame_id = self.cv.create_rectangle(0, 0, 0, 0, outline=GOLD, width=1.6, state="hidden")

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
        if abs(x - x1) <= e and y1 - e < y < y2 + e:
            return ("resize", "edge")
        if abs(x - x2) <= e and y1 - e < y < y2 + e:
            return ("resize", "edge")
        if abs(y - y1) <= e and x1 - e < x < x2 + e:
            return ("resize", "edge")
        if abs(y - y2) <= e and x1 - e < x < x2 + e:
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
                            fill="#111111", tags="sz", font=(FONT, 10, "bold"))
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
            with open(os.path.join(OUT_DIR, "latest.txt"), "w", encoding="utf-8") as f:
                f.write(path)
            # 顺手进剪贴板，直接可以粘贴
            try:
                import subprocess
                subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                                "Set-Clipboard -Path '%s'" % path],
                               capture_output=True, timeout=8,
                               creationflags=0x08000000)
            except Exception:
                pass
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
        if "pet.py" in out:
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
    Pet().root.mainloop()
