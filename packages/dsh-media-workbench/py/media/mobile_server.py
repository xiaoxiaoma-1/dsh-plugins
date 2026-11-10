# -*- coding: utf-8 -*-
"""口袋：手机端独立小服务。

为什么单独起服务：
  DSH 的 Web GUI 用 cookie/session 鉴权，外部带 Bearer 进不去；
  模型网关 8326 只管 /v1。所以给手机单独开一个端口，直接读写 workbench.db。

用法：pythonw mobile_server.py         （开机自启，不弹黑框）
访问：http://<电脑IP>:8788
"""
import io
import json
import os
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

DB = r"E:\desktop\media\workbench.db"
PORT = 8788
LOG = r"E:\desktop\media\_mobile_server.log"

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
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%m-%d %H:%M:%S ") + str(m) + "\n")
    except Exception:
        pass


def _ensure_train_table():
    c = conn()
    try:
        c.execute("create table if not exists train_log(day text, item text, at text)")
        c.commit()
    except Exception:
        pass
    c.close()


def conn():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    return c


PASS_FILE = r"E:\desktop\media\_pocket_pass.txt"
COOKIE_NAME = "pocket_tok"


def _password():
    try:
        return open(PASS_FILE, encoding="utf-8").read().strip()
    except Exception:
        return ""


def _token():
    """用密码+端口派生一个固定 token，不落盘明文 cookie"""
    import hashlib
    pw = _password()
    if not pw:
        return ""
    return hashlib.sha256(("pocket-" + pw + "-8788").encode("utf-8")).hexdigest()[:32]


def _authed(handler):
    ck = handler.headers.get("cookie") or ""
    want = "pocket_tok=" + _token()
    for part in ck.split(";"):
        if part.strip() == want:
            return True
    return False


LOGIN_HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b0e12"><title>口袋 · 登录</title>
<style>html,body{margin:0;height:100%;background:#0b0e12;color:#e6e9ee;
font:15px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
display:flex;align-items:center;justify-content:center;padding:24px}
.box{width:100%;max-width:340px}
h1{font-size:21px;margin:0 0 6px;font-weight:650}
p{font-size:13px;color:#7f8894;margin:0 0 20px;line-height:1.7}
input{width:100%;box-sizing:border-box;padding:14px;border-radius:12px;font-size:17px;
letter-spacing:2px;background:#151a20;color:#e6e9ee;border:1px solid #2b333d;outline:none}
input:focus{border-color:rgba(217,169,74,.6)}
button{width:100%;margin-top:12px;padding:15px;border-radius:12px;font-size:15px;
background:rgba(217,169,74,.16);border:1px solid rgba(217,169,74,.5);color:#f2ce84;
font-family:inherit}
button:active{transform:scale(.98)}
.err{color:#e09182;font-size:13px;margin-top:10px;min-height:18px}</style></head>
<body><div class="box"><h1>口袋</h1>
<p>输入一次密码，这台设备就记住了。</p>
<input id="p" type="password" placeholder="访问密码" autocomplete="current-password">
<button onclick="go()">进去</button><div class="err" id="e"></div></div>
<script>
function go(){
  var v=document.getElementById('p').value.trim();
  if(!v) return;
  fetch('/login',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({p:v})}).then(function(r){return r.json()}).then(function(j){
    if(j.ok){location.reload()} else {document.getElementById('e').textContent='密码不对'}
  }).catch(function(){document.getElementById('e').textContent='连不上'});
}
document.getElementById('p').addEventListener('keydown',function(e){if(e.key==='Enter')go()});
</script></body></html>"""

# ---------------- 数据 ----------------

def api_list(limit=20):
    c = conn()
    # random() 在近万行上排序太慢（真机页面会等超时），改成随机偏移 + 取一段
    import random as _r
    tot = c.execute(
        "select count(*) from atoms a where coalesce(a.hidden,0)=0 "
        "and a.id not in (select coalesce(topic_id,'') from my_views where kind='clash')"
    ).fetchone()[0]
    off = _r.randint(0, max(0, tot - limit - 1)) if tot > limit else 0
    rows = c.execute(
        "select a.id, a.author, a.knowledge from atoms a "
        "where coalesce(a.hidden,0)=0 "
        "and a.id not in (select coalesce(topic_id,'') from my_views where kind='clash') "
        "limit ? offset ?", (limit, off)).fetchall()
    left = c.execute(
        "select count(*) from atoms a where coalesce(a.hidden,0)=0 "
        "and a.id not in (select coalesce(topic_id,'') from my_views where kind='clash')"
    ).fetchone()[0]
    done = c.execute("select count(*) from my_views where kind='clash'").fetchone()[0]
    c.close()
    return {"ok": True, "left": left, "done": done,
            "items": [{"id": r["id"], "author": r["author"], "claim": r["knowledge"]} for r in rows]}


def api_vote(atom_id, verdict, why):
    why = (why or "").strip()
    if not why:
        return {"ok": False, "error": "必须写点什么才能存"}
    c = conn()
    r = c.execute("select author, knowledge from atoms where id=?", (atom_id,)).fetchone()
    src = r["knowledge"] if r else ""
    who = r["author"] if r else ""
    label = {"agree": "认同", "disagree": "不认同"}.get(verdict, "说不清")
    title = label + "「" + src[:24] + "」"
    content = "【我的态度】" + label + "\n【对方观点】" + src + "\n【作者】" + who + "\n【我的理由/延伸】" + why
    vid = "mv_" + str(int(time.time() * 1000))
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "insert into my_views (id,kind,topic_id,title,content,chars,ai_review,status,tags,created_at,updated_at)"
        " values (?,?,?,?,?,?,?,?,?,?,?)",
        (vid, "clash", atom_id, title, content, len(content), "", "saved",
         "对撞," + verdict + "," + atom_id, t, t))
    c.commit()
    c.close()
    return {"ok": True, "view_id": vid}


def api_idea_add(content):
    content = (content or "").strip()
    if not content:
        return {"ok": False, "error": "空的"}
    c = conn()
    iid = "idea" + str(int(time.time() * 1000))[-10:]
    c.execute("insert into ideas (id,source,content,note,tags,status,created_at) values (?,?,?,?,?,?,?)",
              (iid, "mobile", content, "", "", "new", time.strftime("%Y-%m-%dT%H:%M:%S")))
    c.commit()
    c.close()
    return {"ok": True, "id": iid}


def api_ideas(limit=8):
    c = conn()
    rows = c.execute("select id, content, created_at from ideas order by created_at desc limit ?",
                     (limit,)).fetchall()
    c.close()
    return {"ok": True, "ideas": [{"id": r["id"], "content": r["content"]} for r in rows]}


def api_stats():
    c = conn()
    views = c.execute("select count(*) from atoms").fetchone()[0]
    posts = c.execute("select count(*) from posts").fetchone()[0]
    live = c.execute("select count(*) from live_segments").fetchone()[0]
    done = c.execute("select count(*) from my_views where kind='clash'").fetchone()[0]
    ideas = c.execute("select count(*) from ideas").fetchone()[0]
    c.close()
    return {"ok": True, "views": views, "posts": posts, "live": live, "done": done, "ideas": ideas}




def api_undo():
    """撤回最后一次表态：删掉最新一条 clash，并把那条观点还回去。"""
    c = conn()
    r = c.execute(
        "select id, topic_id from my_views where kind='clash' order by created_at desc limit 1"
    ).fetchone()
    if not r:
        c.close()
        return {"ok": False, "error": "还没有表态过，撤不回"}
    vid, atom_id = r["id"], r["topic_id"]
    a = c.execute("select id, author, knowledge from atoms where id=?", (atom_id,)).fetchone()
    c.execute("delete from my_views where id=?", (vid,))
    c.commit()
    left = c.execute(
        "select count(*) from atoms a where coalesce(a.hidden,0)=0 "
        "and a.id not in (select coalesce(topic_id,'') from my_views where kind='clash')"
    ).fetchone()[0]
    c.close()
    item = {"id": a["id"], "author": a["author"], "claim": a["knowledge"]} if a else None
    return {"ok": True, "item": item, "left": left, "done": left * 0 + (0)}


def _wan(n):
    """数字转成万/亿，给手机上看"""
    try:
        n = int(n)
    except Exception:
        return "0"
    if n >= 100000000:
        return "%.1f 亿" % (n / 100000000.0)
    if n >= 10000:
        return "%.1f 万" % (n / 10000.0)
    return str(n)


def api_library_stats():
    """稿库：只出数据。推文/直播/书 各自篇数与字数。"""
    c = conn()
    def one(sql, *a):
        try:
            r = c.execute(sql, a).fetchone()
            return r[0] if r and r[0] is not None else 0
        except Exception:
            return 0
    posts_n = one("select count(*) from posts")
    posts_w = one("select sum(length(coalesce(text,''))) from posts")
    live_n = one("select count(*) from live_segments")
    live_w = one("select sum(length(coalesce(text,''))) from live_segments")
    book_n = one("select count(*) from books")
    chunk_n = one("select count(*) from book_chunks")
    chunk_w = one("select sum(coalesce(chars,0)) from book_chunks")
    atoms_n = one("select count(*) from atoms")
    # 作者数
    au_n = one("select count(distinct author) from atoms where coalesce(author,'')<>''")
    c.close()
    return {"ok": True, "items": [
        {"k": "推文 / 稿子", "n": "%d 篇" % posts_n, "w": _wan(posts_w) + " 字"},
        {"k": "直播逐字稿", "n": "%d 段" % live_n, "w": _wan(live_w) + " 字"},
        {"k": "书", "n": "%d 本" % book_n, "w": _wan(chunk_w) + " 字"},
        {"k": "书块", "n": "%d 块" % chunk_n, "w": ""},
        {"k": "已提炼观点", "n": "%d 条" % atoms_n, "w": "来自 %d 位作者" % au_n},
    ]}


def api_capture_stats():
    """采集台：读 DouyinLiveRecorder 的三个真实状态文件，只出数据不做操作。"""
    import json as _j
    B = r"E:\tools\DouyinLiveRecorder"

    def rd(name, dflt):
        try:
            with open(B + "\\" + name, encoding="utf-8") as f:
                return _j.load(f)
        except Exception:
            return dflt

    fs = rd(".follow_status.json", {})
    ps = rd(".pipeline_status.json", {})
    st = rd(".pipeline_state.json", {})

    live = fs.get("followedLive") or 0
    anchors = len(fs.get("anchors") or [])
    running = len(ps.get("running") or [])
    done_today = ps.get("doneToday") or 0

    st = st if isinstance(st, dict) else {}
    done = 0
    fail = 0
    for v in st.values():
        s = (v or {}).get("status") or ""
        if s == "done":
            done += 1
        elif s in ("wav_fail", "crash", "fail"):
            fail += 1

    # 待转写：录好的视频里还没落状态记录的
    pending = 0
    try:
        import glob
        vids = glob.glob(r"D:\采数据\直播录制\抖音直播\**\*.mp4", recursive=True)
        pending = max(0, len(vids) - len(st))
    except Exception:
        pending = 0

    return {"ok": True, "items": [
        {"k": "关注的主播", "n": str(anchors), "w": "个"},
        {"k": "正在直播", "n": str(live), "w": "个在播"},
        {"k": "正在录制", "n": str(running), "w": "个在录"},
        {"k": "今日完成", "n": str(done_today), "w": "场"},
        {"k": "待转写", "n": str(pending), "w": "份在队列"},
        {"k": "转写中", "n": str(running), "w": "份"},
        {"k": "已转完", "n": str(done), "w": "份"},
        {"k": "失败待重试", "n": str(fail), "w": "份"},
    ]}


def api_topics(limit=30):
    """选题池：照搬列表"""
    c = conn()
    try:
        rows = c.execute(
            "select id, title, coalesce(status,'') st, coalesce(angle,'') note, "
            "coalesce(score,0) sc, coalesce(level,'') lv, coalesce(dims,'') dm, "
            "coalesce(board,'') bd, coalesce(hook,'') hk, coalesce(why,'') wy, "
            "coalesce(extra,'') ex "
            "from pool_topics order by coalesce(score,0) desc, rowid desc limit ?", (limit,)).fetchall()
        out = []
        for r in rows:
            dims = {}
            try:
                import json as _j
                dims = _j.loads(r["dm"]) if r["dm"] else {}
            except Exception:
                dims = {}
            draft_len = 0
            try:
                import json as _jj
                _ex = _jj.loads(r["ex"] or "{}")
                draft_len = len((_ex.get("draft") or ""))
            except Exception:
                draft_len = 0
            out.append({"id": r["id"], "title": r["title"], "status": r["st"], "note": r["note"],
                        "score": r["sc"], "level": r["lv"], "board": r["bd"],
                        "hook": r["hk"], "why": r["wy"], "dims": dims,
                        "hasDraft": draft_len > 0, "draftLen": draft_len})
        total = c.execute("select count(*) from pool_topics").fetchone()[0]
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True, "total": total, "items": out}


def api_myviews(limit=30):
    """我的观点：照搬列表"""
    c = conn()
    try:
        rows = c.execute(
            "select id, title, coalesce(kind,'') kind, coalesce(created_at,'') at, "
            "coalesce(ai_review,'') rev "
            "from my_views order by created_at desc limit ?", (limit,)).fetchall()
        out = []
        for r in rows:
            rv = {}
            try:
                import json as _j
                rv = _j.loads(r["rev"] or "{}") if (r["rev"] or "").strip().startswith("{") else {}
            except Exception:
                rv = {}
            out.append({"id": r["id"], "title": r["title"], "kind": r["kind"],
                        "at": r["at"], "review": rv})
        total = c.execute("select count(*) from my_views").fetchone()[0]
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True, "total": total, "items": out}


def api_view_one(vid):
    """看一条我的观点的全文"""
    c = conn()
    r = c.execute("select id,title,content,created_at from my_views where id=?", (vid,)).fetchone()
    c.close()
    if not r:
        return {"ok": False, "error": "找不到"}
    return {"ok": True, "id": r["id"], "title": r["title"], "content": r["content"], "at": r["created_at"]}

DRAFT_SYSTEM = """你要替一个做知识类内容的自媒体博主，把一条选题写成可以直接开拍的口播稿。

铁律：
- 只用【原始素材】里的事实和观点。素材里没有的数字、案例、经历，一个都不许加。
- 素材不足以支撑这条选题，就直说「素材不够，这条写不了」并说明缺什么，不要硬写。
- 用大白话，第一人称，像在跟同行的朋友讲话。
- 不要「值得注意的是」「意义重大」这类空话，不要「点赞关注」结尾。
"""


def _gw_chat(system, prompt, max_tokens=2600):
    import json as _j
    import urllib.request as _u
    try:
        key = open(r"E:\DSH-data\.dsh\openai-gateway\api-key", encoding="utf-8").read().strip()
    except Exception:
        return None, "读不到网关 key"
    body = _j.dumps({
        "model": "siliconflow/deepseek-ai/DeepSeek-V3.2",
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "temperature": 0.75, "max_tokens": max_tokens,
    }).encode("utf-8")
    try:
        req = _u.Request("http://127.0.0.1:8326/v1/chat/completions", data=body,
                         headers={"content-type": "application/json",
                                  "authorization": "Bearer " + key})
        with _u.urlopen(req, timeout=240) as r:
            j = _j.loads(r.read().decode("utf-8"))
        return (j["choices"][0]["message"]["content"] or "").strip(), None
    except Exception as e:
        return None, str(e)[-180:]


def _src_text(c, kind, ref):
    if not ref:
        return None
    tries = []
    k = (kind or "").lower()
    if k in ("atom", "atoms"):
        tries = [("atoms", "knowledge")]
    elif k in ("post", "posts"):
        tries = [("posts", "text")]
    elif k in ("live", "live_segment", "live_segments"):
        tries = [("live_segments", "text")]
    tries += [("atoms", "knowledge"), ("posts", "text"), ("live_segments", "text")]
    for tb, col in tries:
        try:
            r = c.execute("select %s from %s where id=?" % (col, tb), (ref,)).fetchone()
            if r and r[0]:
                return r[0]
        except Exception:
            pass
    return None


def api_draft(topic_id, rewrite=False):
    import json as _j
    c = conn()
    r = c.execute("select * from pool_topics where id=?", (topic_id,)).fetchone()
    if not r:
        c.close()
        return {"ok": False, "error": "找不到这条选题"}
    t = dict(r)
    # 已缓存
    try:
        ex = _j.loads(t.get("extra") or "{}")
    except Exception:
        ex = {}
    if ex.get("draft") and not rewrite:
        c.close()
        return {"ok": True, "cached": True, "text": ex["draft"]}
    src = _src_text(c, t.get("source_kind"), t.get("source_ref"))
    c.close()
    if not src:
        return {"ok": False, "error": "取不到原始素材，这条写不了"}
    prompt = ("选题：%s\n切入角度：%s\n开头钩子：%s\n\n【原始素材】\n%s"
              % (t.get("title") or "", t.get("angle") or "", t.get("hook") or "",
                 str(src)[:4000]))
    text, err = _gw_chat(DRAFT_SYSTEM, prompt)
    if err:
        return {"ok": False, "error": err}
    if not text:
        return {"ok": False, "error": "AI 返回空"}
    try:
        c2 = conn()
        ex["draft"] = text
        c2.execute("update pool_topics set extra=? where id=?",
                   (_j.dumps(ex, ensure_ascii=False), topic_id))
        c2.commit()
        c2.close()
    except Exception:
        pass
    return {"ok": True, "text": text}


def api_topic_status(topic_id, status):
    if not topic_id or not status:
        return {"ok": False, "error": "缺参数"}
    c = conn()
    try:
        c.execute("update pool_topics set status=? where id=?", (status, topic_id))
        c.commit()
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True}


def api_topic_del(topic_id):
    c = conn()
    try:
        c.execute("delete from pool_topics where id=?", (topic_id,))
        c.commit()
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True}

_JIEBA = None


def _jieba():
    global _JIEBA
    if _JIEBA is None:
        try:
            import jieba as _jb
            import jieba.posseg
            _jb.setLogLevel(20)
            _JIEBA = _jb
        except Exception:
            _JIEBA = False
    return _JIEBA


# 口水词 / 虚词：这些出现频率最高但对"找相关内容"毫无用处
_STOP = set("""其实 我觉 觉得 时候 现在 已经 一个 一样 这样 那样 东西 事情 感觉 真的
可能 一定 全部 有点 比较 非常 特别 地方 方面 问题 情况 的话 这种 那种 一些
一下 只是 还是 或者 并且 不过 于是 因此 什么 怎么样 就是 不是 可以 应该 需要
自己 我们 他们 你们 因为 所以 但是 而且 如果 然后 这个 那个 怎么 知道 认为
开始 之后 之前 起来 出来 过来 下来 上去 一样 一样 人家 这个 那个 到底 到底
是不是 有没有 会不会 能不能 要不要 对不对 好了 行了 算了 罢了 似的 一样""".split())


def _kw_of(text, limit=12):
    """jieba 分词取实词，按词性粗筛 + 去口水词"""
    jb = _jieba()
    text = (text or "").strip()
    if not text:
        return []
    out, seen = [], set()
    if jb:
        # 只留名词/动词/形容词/专名，长度 2 以上
        for w, flag in jb.posseg.cut(text):
            w = w.strip()
            if len(w) < 2 or w in _STOP or w in seen:
                continue
            # n=名词 v=动词 a=形容词 nr/ns=人名地名 j=简称
            if not (flag[0] in ("n", "v", "a") or flag in ("nz", "vn", "an", "eng")):
                continue
            seen.add(w)
            out.append(w)
            if len(out) >= limit:
                break
        if out:
            return out
        # posseg 没结果就退回普通分词
        for w in jb.cut(text):
            w = w.strip()
            if len(w) < 2 or w in _STOP or w in seen:
                continue
            seen.add(w)
            out.append(w)
            if len(out) >= limit:
                break
        return out
    # 没 jieba 时的兜底：3 字窗口
    import re as _re
    for p in _re.split(r"[^\u4e00-\u9fa5]+", text):
        if len(p) < 2:
            continue
        for k in range(len(p) - 2):
            w = p[k:k + 3]
            if w in _STOP or w in seen:
                continue
            seen.add(w)
            out.append(w)
            if len(out) >= limit:
                return out
    return out

def api_match(text):
    """在稿库/直播/观点里找和这段话相关的内容"""
    kws = _kw_of(text)
    if not kws:
        return {"ok": True, "hits": [], "kws": []}
    c = conn()
    cand = {}
    for kw in kws:
        for tb, col, label in (("posts", "text", "稿库"), ("live_segments", "text", "直播"),
                               ("atoms", "knowledge", "观点")):
            try:
                rows = c.execute(
                    "select id, %s from %s where instr(%s, ?) > 0 limit 40" % (col, tb, col),
                    (kw,)).fetchall()
            except Exception:
                continue
            for r in rows:
                key = tb + ":" + str(r["id"])
                cur = cand.get(key)
                if cur:
                    cur["score"] += 1
                    if kw not in cur["kws"]:
                        cur["kws"].append(kw)
                else:
                    txt = (r[col] or "").strip().replace("\n", " ")
                    if len(txt) < 20:
                        continue
                    cand[key] = {"src": label, "tb": tb, "id": r["id"],
                                 "text": txt, "score": 1, "kws": [kw]}
    c.close()
    hits = sorted(cand.values(), key=lambda x: (-x["score"], -sum(len(k) for k in x["kws"])))[:8]
    out = []
    for x in hits:
        t = x["text"]
        # 截一段带关键词的上下文
        kw0 = x["kws"][0] if x["kws"] else ""
        p = t.find(kw0) if kw0 else 0
        st = max(0, p - 40)
        seg = t[st:st + 150]
        out.append({"src": x["src"], "id": x["id"], "seg": seg,
                    "score": x["score"], "kws": x["kws"][:3]})
    return {"ok": True, "hits": out, "kws": kws}


def api_myview_add(content, title):
    """自己写一条观点（原「我的灵感」的功能并进来了）"""
    content = (content or "").strip()
    if not content:
        return {"ok": False, "error": "空的"}
    t = (title or "").strip() or (content[:24] + ("…" if len(content) > 24 else ""))
    c = conn()
    vid = "mv_" + str(int(time.time() * 1000))
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        c.execute(
            "insert into my_views (id,kind,topic_id,title,content,chars,ai_review,status,tags,created_at,updated_at)"
            " values (?,?,?,?,?,?,?,?,?,?,?)",
            (vid, "自写", "", t, content, len(content), "", "saved", "自写", ts, ts))
        c.commit()
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True, "id": vid}

# ★ 临时演示开关：True 时若 0 命中会塞一条真稿库原文，方便看效果
#   看完改回 False 即恢复"没有就说没有"
DEMO_MATCH = True

DEMO_ITEM = {
    "src": "稿库（演示）",
    "id": "demo",
    "seg": "赚钱这个事情，从来都不是有人掌握了财富密码，藏着掖着不说出来。从来都是 1000 个人看见财富密码，1000 个人都当成放 P。你让 1000 个人找对标，1000 个人有 1000 个不找的理由。这就是赚钱的门槛——大家都知道答案，但是大家都说服不了自己。",
    "score": 10,
    "why": "（演示）这段讲的是「知道该赚钱但不去做」，和你说的「年轻时就知道该搞钱却没认真搞」是同一层意思。",
}

MATCH_SYS = """你是一个内容检索助手。用户会给你一句他的主张，以及若干段别人的原文。
你的任务：判断每段原文是不是在讲**同一件事/同一个道理**（不要求说法一样，要求意思对得上）。

判断标准：
- 只要这段原文也是在讲这个道理、给同一个建议、持同一个立场，就算相关。
- 只是碰巧出现同样的词，但讲的不是一回事，不算。
- 宁可漏，不许硬凑。

只输出 JSON：{"hits":[段号,...],"why":{"段号":"一句话说明为什么相关"}}
没有相关的就输出 {"hits":[]}"""


def api_match_semantic(text):
    """两步：先浓缩主张并取概念词，再用 AI 判相关性。"""
    import json as _j
    text = (text or "").strip()
    if not text:
        return {"ok": True, "hits": [], "core": "", "kws": []}

    # ---- 第 1 步：浓缩成一句话 + 取概念词 ----
    p1 = ("把这段话浓缩成一句最核心的主张（15-30字，第一人称），"
          "再给 6 个能拿去搜相关原文的关键词（2-4字的名词或动词）。\n"
          '只输出 JSON：{"core":"一句主张","kws":["词1","词2",...]}\n\n原文：\n' + text[:900])
    out1, err1 = _gw_chat("你是中文文本提炼助手，只输出 JSON。", p1, max_tokens=400)
    if err1:
        return {"ok": False, "error": "提炼失败：" + err1}
    core, kws = text[:40], []
    try:
        import re as _re
        m = _re.search(r"\{[\s\S]*\}", out1 or "")
        if m:
            j1 = _j.loads(m.group(0))
            core = (j1.get("core") or core).strip()
            kws = [str(x).strip() for x in (j1.get("kws") or []) if str(x).strip()][:6]
    except Exception:
        pass
    if not kws:
        kws = _kw_of(text)[:6]

    # ---- 第 2 步：用概念词捞候选 ----
    c = conn()
    cand = {}
    for kw in kws:
        for tb, col, label in (("posts", "text", "稿库"), ("live_segments", "text", "直播"),
                               ("atoms", "knowledge", "观点")):
            try:
                rows = c.execute(
                    "select id, %s from %s where instr(%s, ?) > 0 limit 12" % (col, tb, col),
                    (kw,)).fetchall()
            except Exception:
                continue
            for r in rows:
                key = tb + ":" + str(r["id"])
                if key in cand:
                    continue
                t = (r[col] or "").strip().replace("\n", " ")
                if len(t) < 40:
                    continue
                cand[key] = {"src": label, "id": r["id"], "text": t, "kw": kw}
    c.close()
    items = list(cand.values())[:18]
    if not items:
        demo = [dict(DEMO_ITEM)] if DEMO_MATCH else []
        return {"ok": True, "hits": demo, "core": core, "kws": kws,
                "note": "" if demo else "稿库里没有相关原文"}

    # ---- 第 3 步：让 AI 判相关性 ----
    lines = []
    for i, it in enumerate(items, 1):
        lines.append("%d. %s" % (i, it["text"][:220]))
    p2 = ("我的主张：「%s」\n\n下面是候选原文：\n%s\n\n"
          "哪些段落是在讲同一件事？只挑真的对得上的，宁可漏不许硬凑。" % (core, "\n".join(lines)))
    out2, err2 = _gw_chat(MATCH_SYS, p2, max_tokens=800)
    if err2:
        return {"ok": False, "error": "判相关性失败：" + err2}

    keep, why = [], {}
    try:
        import re as _re
        m = _re.search(r"\{[\s\S]*\}", out2 or "")
        if m:
            j2 = _j.loads(m.group(0))
            keep = [int(x) for x in (j2.get("hits") or []) if str(x).isdigit()]
            why = j2.get("why") or {}
    except Exception:
        pass

    hits = []
    for n in keep:
        if 1 <= n <= len(items):
            it = items[n - 1]
            t = it["text"]
            p = t.find(it["kw"])
            st = max(0, p - 40) if p > 0 else 0
            hits.append({"src": it["src"], "id": it["id"], "seg": t[st:st + 180],
                         "score": 10, "why": str(why.get(str(n)) or why.get(n) or "")})

    if not hits and DEMO_MATCH:
        hits = [dict(DEMO_ITEM)]

    return {"ok": True, "hits": hits[:6], "core": core, "kws": kws,
            "note": "" if hits else "稿库里没有真正讲同一件事的原文"}

PERSONAS_FILE = r"E:\desktop\media\personas.json"
ROUNDTABLE_FILE = r"E:\desktop\media\roundtable.json"


def _read_json(path, dflt):
    import json as _j
    try:
        with open(path, encoding="utf-8") as f:
            return _j.load(f)
    except Exception:
        return dflt


def api_personas():
    """分身：8 位顾问"""
    j = _read_json(PERSONAS_FILE, {})
    ps = j.get("personas") if isinstance(j, dict) else None
    if not ps:
        return {"ok": True, "items": []}
    out = []
    for p in ps:
        out.append({
            "id": p.get("id") or "",
            "name": p.get("name") or "",
            "title": p.get("title") or "",
            "focus": p.get("focus") or "",
            "frame": p.get("frame") or "",
            "voice": p.get("voice") or "",
            "against": p.get("against") or "",
        })
    return {"ok": True, "items": out}


def api_roundtable():
    """圆桌会议：一次提问，多个分身同时表态"""
    j = _read_json(ROUNDTABLE_FILE, {})
    ts = j.get("topics") if isinstance(j, dict) else None
    if not ts:
        return {"ok": True, "items": [], "total": 0}
    out = []
    for t in ts:
        out.append({
            "id": t.get("id") or "",
            "topic": t.get("topic") or t.get("title") or "",
            "at": t.get("at") or t.get("created_at") or "",
            "turns": len(t.get("turns") or t.get("rounds") or []),
        })
    out.sort(key=lambda x: x.get("at") or "", reverse=True)
    return {"ok": True, "items": out, "total": len(out)}


def api_corpus(limit=40):
    """我的语料库：只出不进的私有版本，取 my_views 里非表态的"""
    c = conn()
    try:
        rows = c.execute(
            "select id, title, coalesce(kind,'') kind, coalesce(chars,0) chars, "
            "coalesce(created_at,'') at from my_views "
            "where instr(coalesce(tags,''), '语料') > 0 "
            "order by created_at desc limit ?", (limit,)).fetchall()
        out = [{"id": r["id"], "title": r["title"], "kind": r["kind"],
                "chars": r["chars"], "at": r["at"]} for r in rows]
        total = c.execute(
            "select count(*) from my_views where instr(coalesce(tags,''), '语料') > 0"
        ).fetchone()[0]
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True, "total": total, "items": out}

# ---------------- AI 写的异步任务 ----------------
import threading as _th
import time as _tm

_TASKS = {}          # task_id -> {"state":"running|done|error","text":"","error":""}
_TASK_LOCK = _th.Lock()


def _run_draft_task(task_id, topic_id, rewrite):
    try:
        r = api_draft(topic_id, rewrite)
        with _TASK_LOCK:
            if r.get("ok"):
                _TASKS[task_id] = {"state": "done", "text": r.get("text") or "", "error": ""}
            else:
                _TASKS[task_id] = {"state": "error", "text": "", "error": r.get("error") or "写不出来"}
    except Exception as e:
        with _TASK_LOCK:
            _TASKS[task_id] = {"state": "error", "text": "", "error": str(e)[-200:]}


def api_draft_start(topic_id, rewrite=False):
    """立刻返回 task_id，后台去写。手机端拿 id 轮询，不用挂长连接。"""
    if not topic_id:
        return {"ok": False, "error": "缺少选题 id"}
    tid = "t" + str(int(_tm.time() * 1000))[-11:]
    with _TASK_LOCK:
        _TASKS[tid] = {"state": "running", "text": "", "error": ""}
        # 顺手清理 10 分钟前的旧任务
        now = _tm.time()
        for k in [k for k, v in _TASKS.items() if v.get("_at") and now - v["_at"] > 600]:
            _TASKS.pop(k, None)
    th = _th.Thread(target=_run_draft_task, args=(tid, topic_id, rewrite), daemon=True)
    th.start()
    return {"ok": True, "task": tid}


def api_draft_status(task_id):
    with _TASK_LOCK:
        v = _TASKS.get(task_id)
    if not v:
        return {"ok": False, "error": "任务不存在或已过期"}
    if v["state"] == "running":
        return {"ok": True, "state": "running"}
    if v["state"] == "error":
        return {"ok": False, "state": "error", "error": v.get("error") or "写不出来"}
    return {"ok": True, "state": "done", "text": v.get("text") or ""}

# ---------------- 分身对话 / 圆桌会议 ----------------
def _persona_prompt(p, question, atoms):
    src = "\n".join("[%d] %s" % (i + 1, str(a)[:120]) for i, a in enumerate(atoms or []))
    return ("""你是「%s」，%s。

你的知识来自用户精选的商业博主内容库，下面是与本次问题相关的素材（可能与问题不完全相关，无关就无视，不要硬套）：
%s

你的关注点：%s
你的判断框架：%s
你的说话方式：%s
你明确反对：%s

用户问：%s

用你的角度回答，200 字以内，口语，不要分点、不要标题、不要 markdown。只讲你自己的看法，不要替别人总结。"""
            % (p.get("name") or "", p.get("title") or "",
               src or "（本次没有检索到明显相关的素材）",
               p.get("focus") or "", p.get("frame") or "",
               p.get("voice") or "", p.get("against") or "", question))


def _search_atoms(question, limit=6):
    """从观点库里捞和问题相关的素材"""
    kws = _kw_of(question, 6)
    if not kws:
        return []
    c = conn()
    seen, out = set(), []
    for kw in kws:
        try:
            rows = c.execute(
                "select id, knowledge from atoms where coalesce(hidden,0)=0 "
                "and instr(knowledge, ?) > 0 limit 8", (kw,)).fetchall()
        except Exception:
            continue
        for r in rows:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            out.append(r["knowledge"])
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break
    c.close()
    return out


def api_persona_chat(persona_id, question):
    question = (question or "").strip()
    if not question:
        return {"ok": False, "error": "先写个问题"}
    ps = api_personas().get("items") or []
    p = next((x for x in ps if x["id"] == persona_id), None)
    if not p:
        return {"ok": False, "error": "找不到这个角色"}
    atoms = _search_atoms(question, 6)
    text, err = _gw_chat(
        "你是一个有明确立场的顾问，说话口语、短句、不客套。",
        _persona_prompt(p, question, atoms), max_tokens=700)
    if err:
        return {"ok": False, "error": "问不出来：" + err}
    return {"ok": True, "text": text, "persona": p.get("name"),
            "sources": atoms[:4]}


def api_roundtable_open(question, persona_ids=None):
    """开一场圆桌：多个分身同时表态（顺序跑，避免打爆网关）"""
    import threading as _th
    import time as _tm
    question = (question or "").strip()
    if not question:
        return {"ok": False, "error": "先写个议题"}
    ps = api_personas().get("items") or []
    if persona_ids:
        picked = [x for x in ps if x["id"] in persona_ids][:6]
    else:
        picked = ps[:5]
    if not picked:
        return {"ok": False, "error": "没有可用分身"}
    atoms = _search_atoms(question, 8)

    tid = "rt" + str(int(_tm.time() * 1000))[-10:]
    with _TASK_LOCK:
        _TASKS[tid] = {"state": "running", "question": question, "answers": [],
                       "done": 0, "total": len(picked)}

    def run():
        answers = []
        for p in picked:
            try:
                txt, err = _gw_chat(
                    "你是顾问团的一员，只讲你这一角度的看法，允许和其他顾问冲突。",
                    _persona_prompt(p, question, atoms), max_tokens=600)
                answers.append({"name": p.get("name"), "title": p.get("title"),
                                "text": (txt or "").strip(), "error": err or ""})
            except Exception as e:
                answers.append({"name": p.get("name"), "title": p.get("title"),
                                "text": "", "error": str(e)[-120:]})
            with _TASK_LOCK:
                _TASKS[tid]["answers"] = list(answers)
                _TASKS[tid]["done"] = len(answers)
        with _TASK_LOCK:
            _TASKS[tid]["state"] = "done"
        # 落盘留档
        try:
            import json as _j
            j = _read_json(ROUNDTABLE_FILE, {"version": 1, "topics": []})
            if not isinstance(j, dict):
                j = {"version": 1, "topics": []}
            j.setdefault("topics", []).append({
                "id": tid, "topic": question, "at": _tm.strftime("%Y-%m-%d %H:%M:%S"),
                "answers": answers,
            })
            with open(ROUNDTABLE_FILE, "w", encoding="utf-8") as f:
                _j.dump(j, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    _th.Thread(target=run, daemon=True).start()
    return {"ok": True, "task": tid, "total": len(picked)}


def api_roundtable_status(task_id):
    with _TASK_LOCK:
        v = _TASKS.get(task_id)
    if not v:
        return {"ok": False, "error": "任务不存在或已过期"}
    return {"ok": True, "state": v.get("state"), "question": v.get("question"),
            "answers": v.get("answers") or [], "done": v.get("done") or 0,
            "total": v.get("total") or 0}

VIEW_SYSTEM = """你是严格的写作教练。用户会给你一段他自己写的观点，你要评它，不是改它。

铁律：
- 一个字都不许改他的原文，也不许给"改写版本""示范段落"。给了就是违约。
- 你只指出：哪里立得住、哪里是空话、哪里缺证据、哪个反问能把人问住。
- 用大白话，不用"值得注意的是""意义重大"。

严格只输出 JSON，不要 markdown，不要解释。格式：
{
  "score": 0-100 的整数（这段能不能当视频论点直接输出）,
  "verdict": "能立住" 或 "半立住" 或 "立不住",
  "pros": ["最多 3 条，具体到句子"],
  "gaps": ["最多 3 条，说清缺什么：缺例子/缺数字/缺因果/是结论不是判断"],
  "questions": ["最多 3 条能把这个观点问深的问句"],
  "one_line": "一句话总评，30 字以内"
}"""


def _parse_json(raw):
    import json as _j
    import re as _re
    m = _re.search(r"\{[\s\S]*\}", raw or "")
    if not m:
        return None
    try:
        return _j.loads(m.group(0))
    except Exception:
        return None


def api_view_review(view_id):
    """让 AI 评一下：只评不改"""
    if not view_id:
        return {"ok": False, "error": "缺少 id"}
    c = conn()
    r = c.execute("select content from my_views where id=?", (view_id,)).fetchone()
    c.close()
    if not r:
        return {"ok": False, "error": "读不到这条观点"}
    content = (r["content"] or "").strip()
    if not content:
        return {"ok": False, "error": "原文是空的"}
    prompt = "下面是我自己写的观点，请评它。原文一个字都不要改，也不要给我改写版。\n\n" + content
    raw, err = _gw_chat(VIEW_SYSTEM, prompt, max_tokens=1600)
    if err:
        return {"ok": False, "error": "评不了：" + err}
    obj = _parse_json(raw)
    if not obj:
        return {"ok": False, "error": "模型输出读不出来"}
    review = {
        "score": max(0, min(100, int(obj.get("score") or 0))),
        "verdict": str(obj.get("verdict") or "")[:20],
        "pros": [str(x)[:200] for x in (obj.get("pros") or [])][:3],
        "gaps": [str(x)[:200] for x in (obj.get("gaps") or [])][:3],
        "questions": [str(x)[:200] for x in (obj.get("questions") or [])][:3],
        "one_line": str(obj.get("one_line") or "")[:80],
    }
    # 存回库
    try:
        import json as _j
        c2 = conn()
        c2.execute("update my_views set ai_review=? where id=?",
                   (_j.dumps(review, ensure_ascii=False), view_id))
        c2.commit()
        c2.close()
    except Exception:
        pass
    return {"ok": True, "review": review}


def api_view_del(view_id):
    if not view_id:
        return {"ok": False, "error": "缺少 id"}
    c = conn()
    try:
        c.execute("delete from my_views where id=?", (view_id,))
        c.commit()
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True}


def api_roundtable_get(task_id):
    """看某一场圆桌的完整内容"""
    import json as _j
    j = _read_json(ROUNDTABLE_FILE, {})
    ts = (j.get("topics") if isinstance(j, dict) else None) or []
    for t in ts:
        if t.get("id") == task_id:
            return {"ok": True, "topic": t.get("topic") or "", "at": t.get("at") or "",
                    "answers": t.get("answers") or [],
                    "rounds": _rt_rounds(t), "followups": t.get("followups") or []}
    # 内存里还在跑的
    with _TASK_LOCK:
        v = _TASKS.get(task_id)
    if v:
        return {"ok": True, "topic": v.get("question") or "", "at": "",
                "answers": v.get("answers") or []}
    return {"ok": False, "error": "找不到这一场"}

POLISH_SYSTEM = """你在帮一个内容创作者练写作。他想看看：同一段内容，更顺的表达长什么样，好对比自己的文风。

铁律（违反即失败）：
- 他的观点、例子、判断、立场，一个都不许加、不许删、不许改方向。
- 保留他的说话习惯：口语就保持口语，别改成书面语；长短句节奏跟着他走。
- 只处理这几件事：啰嗦、绕、重复、前后顺序乱、指代不清。
- 不许加金句、不许升华结尾、不许变成公众号腔、不许加"值得注意的是"这类词。
- 不许加标题、不许分点、不许 markdown。

直接输出润色后的正文，不要任何解释、不要前后缀。"""


def api_speech_polish(text):
    """表达训练里的 AI 润色：直接给一段文字，返回润色版（不入库）"""
    text = (text or "").strip()
    if len(text) < 15:
        return {"ok": False, "error": "太短了，说几句再润色"}
    out, err = _gw_chat(POLISH_SYSTEM, "下面是他的原话，请润色：\n\n" + text, max_tokens=1600)
    if err:
        return {"ok": False, "error": "润不了：" + err}
    return {"ok": True, "text": (out or "").strip(), "orig": text}


def api_view_polish(view_id):
    if not view_id:
        return {"ok": False, "error": "缺少 id"}
    c = conn()
    r = c.execute("select content from my_views where id=?", (view_id,)).fetchone()
    c.close()
    if not r:
        return {"ok": False, "error": "读不到这条观点"}
    content = (r["content"] or "").strip()
    if not content:
        return {"ok": False, "error": "原文是空的"}
    prompt = "下面是他的原话，请润色：\n\n" + content
    text, err = _gw_chat(POLISH_SYSTEM, prompt, max_tokens=1600)
    if err:
        return {"ok": False, "error": "润不了：" + err}
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "AI 返回空"}
    return {"ok": True, "polished": text, "original": content}

def api_corpus_add(view_id, on=True):
    """手动放进/移出我的语料库（用 tags 里的「语料」标记）"""
    if not view_id:
        return {"ok": False, "error": "缺少 id"}
    c = conn()
    r = c.execute("select tags from my_views where id=?", (view_id,)).fetchone()
    if not r:
        c.close()
        return {"ok": False, "error": "找不到这条"}
    tags = [x.strip() for x in (r["tags"] or "").split(",") if x.strip()]
    has = "语料" in tags
    if on and not has:
        tags.append("语料")
    elif not on and has:
        tags = [x for x in tags if x != "语料"]
    try:
        c.execute("update my_views set tags=?, updated_at=? where id=?",
                  (",".join(tags), time.strftime("%Y-%m-%d %H:%M:%S"), view_id))
        c.commit()
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True, "inCorpus": on}


def api_corpus_flags():
    """哪些已经在语料库里（给列表打标记用）"""
    c = conn()
    try:
        rows = c.execute("select id from my_views where instr(coalesce(tags,''), '语料') > 0").fetchall()
        ids = [r["id"] for r in rows]
    except Exception:
        ids = []
    c.close()
    return {"ok": True, "ids": ids}


def api_view_replace(view_id, content):
    """把润色版替换成新原文"""
    content = (content or "").strip()
    if not view_id or not content:
        return {"ok": False, "error": "缺参数"}
    c = conn()
    try:
        c.execute("update my_views set content=?, chars=?, updated_at=? where id=?",
                  (content, len(content), time.strftime("%Y-%m-%d %H:%M:%S"), view_id))
        c.commit()
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True}

# ================= 表达训练 =================
# 词库：全部本地匹配，零 API、零延迟、零费用
FILLER = ["嗯", "呃", "额", "啊", "那个", "然后", "就是", "这个", "呢", "吧", "嘛",
          "其实", "反正", "总之", "所以说", "的话", "对吧", "是不是", "你懂吗",
          "怎么说", "我觉得吧", "这样子", "那种", "完了以后", "就是说"]

HEDGE = ["可能", "我觉得", "应该是", "大概", "也许", "好像", "差不多", "相对来说",
         "某种程度上", "一定程度上", "大概可能", "或许", "估计", "应该是吧",
         "我个人认为", "不一定", "看情况", "应该可以", "有可能"]

# 笼统词 → 具体化的追问
VAGUE = {
    "很多东西": "具体是哪几样",
    "挺好": "好在哪",
    "不错": "哪一点不错",
    "很多": "给个数字",
    "一些": "几个",
    "各种": "哪些",
    "什么的": "列出具体的",
    "之类": "说清楚是什么",
    "有点": "到什么程度",
    "比较": "比什么、差多少",
    "非常": "具体到什么程度",
    "特别": "具体哪一点",
    "很厉害": "厉害在哪",
    "有效": "数据呢",
    "挺好用": "解决了他哪个动作",
    "有价值": "对谁有价值、值多少",
    "很高": "高多少",
    "很低": "低多少",
    "很多钱": "多少钱",
    "大部分人": "百分之多少",
    "很多人": "多少人",
    "大家都": "谁们",
    "一般来说": "什么情况下例外",
    "基本": "差多少算基本",
    "大部分": "百分之几",
}

# 有力表达：数字 + 量词、明确动词、结论句
POWER_UNITS = ["个", "条", "篇", "元", "块", "万", "亿", "倍", "天", "周", "月", "年",
               "小时", "分钟", "秒", "次", "遍", "人", "份", "本", "张", "块钱", "万元",
               "%", "％", "点", "成"]

# 明确动词（说了就是动作，不是感想）
POWER_VERBS = ["做了", "写了", "发了", "赚了", "亏了", "涨了", "跌了", "跑了",
               "测了", "试了", "砍掉", "删掉", "加上", "换成", "改成", "提炼",
               "压到", "做到", "搞到", "省下", "花掉", "投了", "录了", "剪了"]

# 结论句式（有判断，不是和稀泥）
POWER_MARKS = ["所以我", "结论是", "我认为", "我的判断", "说白了", "本质是",
               "核心是", "一句话", "关键是", "必须", "一定得", "不能"]


def _power_hits(text):
    """找有力表达：数字+量词、明确动词、结论标记。返回 (词, 类别) 列表"""
    import re as _re
    out = []
    # 数字 + 量词
    for m in _re.finditer(r"\d+(?:\.\d+)?\s*(?:%|％)?" + "|" +
                          r"\d+(?:\.\d+)?\s*(?:" + "|".join(POWER_UNITS) + ")", text):
        out.append((m.group(0), "power"))
    for w in POWER_VERBS:
        if w in text:
            out.append((w, "power"))
    for w in POWER_MARKS:
        if w in text:
            out.append((w, "power"))
    return out


def _seg(text):
    """最长匹配切词（照搬原项目思路：只认词表里的词，其余按字走）"""
    out = []
    i = 0
    n = len(text)
    dic = {}
    for w in FILLER:
        dic[w] = "filler"
    for w in HEDGE:
        dic[w] = "hedge"
    for w in VAGUE.keys():
        dic[w] = "vague"
    maxlen = max((len(k) for k in dic.keys()), default=2)
    while i < n:
        hit = None
        for L in range(min(maxlen, n - i), 1, -1):
            w = text[i:i + L]
            if w in dic:
                hit = (w, dic[w])
                break
        if hit:
            out.append(hit)
            i += len(hit[0])
        else:
            out.append((text[i], "plain"))
            i += 1
    return out


def api_speech_analyze(text):
    """本地分析：标色 + 词频 + 密度。不发任何 AI 请求。"""
    text = (text or "").strip()
    if not text:
        return {"ok": True, "segs": [], "counts": {"filler": 0, "hedge": 0, "vague": 0},
                "density": 0, "total": 0}
    segs = _seg(text)
    counts = {"filler": 0, "hedge": 0, "vague": 0, "power": 0}
    for w, k in segs:
        if k in counts:
            counts[k] += 1
    # 有力表达：单独扫一遍（它不在切词表里，因为要识别数字+量词组合）
    for w, k in _power_hits(text):
        counts["power"] += 1
        segs.append((w, "power"))
    total = len([1 for w, k in segs if k == "plain" or k in counts])
    used = counts["filler"] + counts["hedge"]
    density = round((total - used) / total * 100) if total else 0
    # 笼统词替换建议
    sug = []
    for w, k in segs:
        if k == "vague" and len(sug) < 6:
            sug.append({"word": w, "ask": VAGUE.get(w, "")})
    return {"ok": True,
            "segs": [{"w": w, "k": k} for w, k in segs],
            "counts": counts, "density": density, "total": total,
            "suggest": sug}


TIP_SYS = """你是中文口语表达的实时教练。每次只输出 1 条提示，不超过 8 个字，不加标点，不解释。

按优先级检查，只输出第一个命中的：
1. 同一意思说了两遍 → 说过一遍
2. 讲了很久没给结论 → 说结论
3. 自问自答形成结构 → ✓ 好结构
4. 连续抽象没数字 → 太抽象给数字
5. 主题漂移 → 跑题
6. 立场模糊 → 你到底觉得呢
7. 全是铺垫 → 砍铺垫
8. 有具体例子 → ✓ 有例子
9. 有明确数字 → ✓ 有数字
10. 语速过赶没停顿 → 停一下
11. 全没命中 → 输出空行

正负反馈混着来，不要偏向某一种。没有触发就输出空行，不硬找话说。"""


def api_speech_tip(text, tail=500):
    """判断性反馈才给 AI：一条不超过 8 字的提示"""
    t = (text or "").strip()[-tail:]
    if not t:
        return {"ok": True, "tip": ""}
    cfg = _sp_cfg()
    sys_p = (cfg.get("tipSystem") or "").strip() or TIP_SYS
    out, err = _gw_chat(_inject(sys_p, cfg), "以下是他说的话：\n" + t, max_tokens=60)
    if err:
        return {"ok": False, "error": err}
    tip = (out or "").strip().splitlines()[0][:12] if (out or "").strip() else ""
    return {"ok": True, "tip": tip}


REPORT_SYS = """你是表达教练。用户刚做完一次口语表达练习，你要给一份六维分析报告。

只看他说的内容，不编造。严格只输出 JSON：
{
  "scores": {"逻辑": 0-100, "直接性": 0-100, "填充词": 0-100, "表达密度": 0-100, "词汇": 0-100, "亮点": 0-100},
  "one_line": "一句话总评，30 字以内",
  "good": ["最多 3 条，具体到他说的哪句话"],
  "fix": ["最多 3 条，具体怎么改"],
  "next": "下一次练习该盯住的一件事，20 字以内"
}
填充词和表达密度这两维按实际比例给分，不夸大。"""


def api_speech_report(text, filler=0, hedge=0, density=0):
    """六维报告：这是判断性任务，给 AI"""
    text = (text or "").strip()
    if len(text) < 30:
        return {"ok": False, "error": "说得太短了，多讲几句再出报告"}
    prompt = ("他的原话：\n%s\n\n本地统计：填充词 %d 次，犹豫词 %d 次，表达密度 %d%%"
              % (text[:3000], filler, hedge, density))
    cfg = _sp_cfg()
    sys_p = (cfg.get("reportSystem") or "").strip() or REPORT_SYS
    out, err = _gw_chat(_inject(sys_p, cfg), prompt, max_tokens=1400)
    if err:
        return {"ok": False, "error": "出报告失败：" + err}
    obj = _parse_json(out)
    if not obj:
        return {"ok": False, "error": "报告读不出来"}
    return {"ok": True, "report": obj}

ROUND_SYS = "你们在开圆桌会议。允许直接反驳别人；没有新观点时可以只回 PASS 表示这轮不发言。"


def _rt_rounds(t):
    """兼容新旧两种存储：旧的是 answers，新的是 rounds"""
    if t.get("rounds"):
        return t["rounds"]
    a = t.get("answers") or []
    return [{"round": 1, "answers": a, "silent": []}] if a else []


def _rt_save(topic_id, t):
    import json as _j
    j = _read_json(ROUNDTABLE_FILE, {"version": 1, "topics": []})
    if not isinstance(j, dict):
        j = {"version": 1, "topics": []}
    ts = j.setdefault("topics", [])
    for i, x in enumerate(ts):
        if x.get("id") == topic_id:
            ts[i] = t
            break
    else:
        ts.append(t)
    try:
        with open(ROUNDTABLE_FILE, "w", encoding="utf-8") as f:
            _j.dump(j, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _assert_done(task, tid, payload):
    with _TASK_LOCK:
        cur = _TASKS.get(tid) or {}
        cur.update(payload)
        cur["state"] = "done"
        _TASKS[tid] = cur


def api_roundtable_next(topic_id):
    """再聊一轮：全员重新举手，允许反驳，允许 PASS"""
    import threading as _th
    import time as _tm
    if not topic_id:
        return {"ok": False, "error": "缺少议题 id"}
    j = _read_json(ROUNDTABLE_FILE, {})
    ts = (j.get("topics") if isinstance(j, dict) else None) or []
    t = next((x for x in ts if x.get("id") == topic_id), None)
    if not t:
        return {"ok": False, "error": "找不到这个议题"}
    rounds = _rt_rounds(t)
    last = rounds[-1] if rounds else None
    if not last:
        return {"ok": False, "error": "还没有上一轮"}
    ps = api_personas().get("items") or []
    atoms = _search_atoms(t.get("topic") or "", 8)

    tid = "rtn" + str(int(_tm.time() * 1000))[-10:]
    with _TASK_LOCK:
        _TASKS[tid] = {"state": "running", "answers": [], "silent": [],
                       "done": 0, "total": len(ps)}

    def run():
        prev = last.get("answers") or []
        answers, silent = [], []
        for p in ps:
            others = "\n".join("%s：%s" % (x.get("name"), (x.get("text") or "")[:220])
                               for x in prev if x.get("name") != p.get("name"))
            src = "\n".join("[%d] %s" % (i + 1, str(a)[:110]) for i, a in enumerate(atoms)) or "（无）"
            prompt = ("议题：%s\n\n上一轮别人说的：\n%s\n\n库内相关素材：\n%s\n\n"
                      "你是「%s」，%s。关注点：%s；框架：%s；腔调：%s；反对：%s\n\n"
                      "这是第 %d 轮。接着上一轮往下说：可以反驳别人，可以补新角度；"
                      "如果这一轮你没有新东西可说，就只输出 PASS。"
                      % (t.get("topic") or "", others or "（无）", src,
                         p.get("name") or "", p.get("title") or "",
                         p.get("focus") or "", p.get("frame") or "",
                         p.get("voice") or "", p.get("against") or "",
                         len(rounds) + 1))
            try:
                txt, err = _gw_chat(ROUND_SYS, prompt, max_tokens=1100)
                txt = (txt or "").strip()
                if err:
                    answers.append({"name": p.get("name"), "title": p.get("title"),
                                    "text": "", "error": err[:120]})
                elif (txt.upper().startswith("PASS") or
                      (len(txt) <= 12 and "PASS" in txt.upper())):
                    silent.append(p.get("name"))
                else:
                    answers.append({"name": p.get("name"), "title": p.get("title"), "text": txt})
            except Exception as e:
                answers.append({"name": p.get("name"), "title": p.get("title"),
                                "text": "", "error": str(e)[-100:]})
            with _TASK_LOCK:
                cur = _TASKS.get(tid) or {}
                cur.update({"answers": list(answers), "silent": list(silent),
                            "done": len(answers) + len(silent)})
                _TASKS[tid] = cur

        rounds.append({"round": len(rounds) + 1, "answers": answers, "silent": silent})
        t["rounds"] = rounds
        _rt_save(topic_id, t)
        _assert_done(None, tid, {"answers": answers, "silent": silent})

    _th.Thread(target=run, daemon=True).start()
    return {"ok": True, "task": tid, "total": len(ps), "round": len(rounds) + 1}


def api_roundtable_ask(topic_id, persona_id, question):
    """追问某一位顾问（可以针对某一轮/某一句继续深挖）"""
    import time as _tm
    question = (question or "").strip()
    if not question:
        return {"ok": False, "error": "先写要问什么"}
    j = _read_json(ROUNDTABLE_FILE, {})
    ts = (j.get("topics") if isinstance(j, dict) else None) or []
    t = next((x for x in ts if x.get("id") == topic_id), None)
    if not t:
        return {"ok": False, "error": "找不到这个议题"}
    ps = api_personas().get("items") or []
    p = next((x for x in ps if x["id"] == persona_id), None)
    if not p:
        return {"ok": False, "error": "找不到这个顾问"}
    # 把他的历史发言带上
    hist = []
    for rd in _rt_rounds(t):
        for a in (rd.get("answers") or []):
            if a.get("name") == p.get("name"):
                hist.append("第%d轮你说了：%s" % (rd.get("round", 1), (a.get("text") or "")[:240]))
    atoms = _search_atoms(question + " " + (t.get("topic") or ""), 6)
    src = "\n".join("[%d] %s" % (i + 1, str(a)[:110]) for i, a in enumerate(atoms)) or "（无）"
    prompt = ("议题：%s\n\n%s\n\n库内相关素材：\n%s\n\n"
              "你是「%s」，%s。关注点：%s；框架：%s；腔调：%s；反对：%s\n\n"
              "用户追问：%s\n\n直接回答，可以展开细说。长度按需要，别凑字数也别自我压缩。不要分点。"
              % (t.get("topic") or "", "\n".join(hist) or "（你还没在这个议题上发过言）",
                 src, p.get("name") or "", p.get("title") or "",
                 p.get("focus") or "", p.get("frame") or "",
                 p.get("voice") or "", p.get("against") or "", question))
    txt, err = _gw_chat("你在圆桌会议上被单独追问，直接回答，允许展开。", prompt, max_tokens=1200)
    if err:
        return {"ok": False, "error": "问不出来：" + err}
    t.setdefault("followups", []).append({
        "personaId": p.get("id"), "name": p.get("name"), "question": question,
        "answer": (txt or "").strip(), "at": _tm.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _rt_save(topic_id, t)
    return {"ok": True, "name": p.get("name"), "answer": (txt or "").strip()}


def api_roundtable_del(topic_id):
    import json as _j
    j = _read_json(ROUNDTABLE_FILE, {})
    if not isinstance(j, dict):
        return {"ok": False, "error": "数据坏了"}
    ts = j.get("topics") or []
    j["topics"] = [x for x in ts if x.get("id") != topic_id]
    try:
        with open(ROUNDTABLE_FILE, "w", encoding="utf-8") as f:
            _j.dump(j, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True}

# ---------------- 表达训练的四个注入点（照搬原项目设计） ----------------
SPEECH_SETTINGS = r"E:\desktop\media\_speech_settings.json"

DEFAULT_SETTINGS = {
    "goals": "",          # 训练目标
    "customRules": "",    # 自定义规则
    "styleRef": "",       # 想要的风格范本
    "customWords": "",    # 自己的口癖词表（逗号分隔，会额外标红）
    "tipSystem": "",      # prompt 编辑器里改过的提示 prompt（空 = 用默认）
    "reportSystem": "",   # 报告 prompt
}


def api_speech_settings_get():
    import json as _j
    try:
        with open(SPEECH_SETTINGS, encoding="utf-8") as f:
            cur = _j.load(f)
    except Exception:
        cur = {}
    out = dict(DEFAULT_SETTINGS)
    out.update(cur or {})
    out["_defaultTip"] = TIP_SYS
    out["_defaultReport"] = REPORT_SYS
    return {"ok": True, "settings": out}


def api_speech_settings_save(obj):
    import json as _j
    try:
        with open(SPEECH_SETTINGS, encoding="utf-8") as f:
            cur = _j.load(f)
    except Exception:
        cur = {}
    for k in DEFAULT_SETTINGS.keys():
        if k in (obj or {}):
            cur[k] = str(obj[k] or "")
    try:
        with open(SPEECH_SETTINGS, "w", encoding="utf-8") as f:
            _j.dump(cur, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True}


def _sp_cfg():
    import json as _j
    try:
        with open(SPEECH_SETTINGS, encoding="utf-8") as f:
            return _j.load(f) or {}
    except Exception:
        return {}


def _inject(base, cfg):
    """把四个注入点拼到 system prompt 末尾"""
    parts = [base]
    if (cfg.get("goals") or "").strip():
        parts.append("训练目标：%s" % cfg["goals"].strip())
    if (cfg.get("customRules") or "").strip():
        parts.append("额外规则：%s" % cfg["customRules"].strip())
    if (cfg.get("styleRef") or "").strip():
        parts.append("他想要的风格范本：%s" % cfg["styleRef"].strip())
    if (cfg.get("customWords") or "").strip():
        parts.append("他自己列的易犯口癖词：%s" % cfg["customWords"].strip())
    return "\n\n".join(parts)


def api_speech_custom_hits(text):
    """用他自己的口癖词表额外标一次"""
    cfg = _sp_cfg()
    words = [x.strip() for x in (cfg.get("customWords") or "").replace("，", ",").split(",") if x.strip()]
    hits = []
    t = text or ""
    for w in words:
        n = t.count(w)
        if n:
            hits.append({"w": w, "n": n})
    return {"ok": True, "hits": hits, "words": words}

# ================= 七种训练（出题 → 你答 → AI 评） =================
TRAIN_CFG = {
    "topic": {
        "name": "话题即兴",
        "sys": "你是口播教练。用户要在 60 秒内讲清对一个观点或话题的看法。你要评他的表达，不改写。",
        "ask": "给一个能立刻开讲的话题或观点，一句话，20 字以内。只输出这一句，不要解释。",
        "judge": (
            "严格只输出 JSON：{\"score\":0-100,"
            "\"good\":[\"最多2条，具体到他说的哪句\"],"
            "\"fix\":[\"最多2条，具体怎么改\"],"
            "\"one_line\":\"一句话总评，30字以内\"}\n"
            "评的维度：有没有明确立场、有没有理由支撑、有没有具体例子、有没有说清。"
        ),
    },
    "retell": {
        "name": "限时复述",
        "sys": "你是复述训练教练。用户看了 30 秒材料，然后合上复述要点。你要比对要点覆盖率。",
        "ask": "给一段 150-250 字的中文材料（真实观点、有 3-5 个要点），只输出材料本身。",
        "judge": (
            "严格只输出 JSON：{\"score\":0-100,"
            "\"kept\":[\"他复述对的关键点\"],"
            "\"missed\":[\"他漏掉的关键点\"],"
            "\"one_line\":\"一句话总评，30字以内\"}\n"
            "分数按要点覆盖比例给，不夸大。"
        ),
    },
    "debate": {
        "name": "反方辩论",
        "sys": "你是辩论教练。用户拿到一个立场，任务是站反方把它推翻。你要评他的论证。",
        "ask": "给一个有争议但成立的立场，一句话，20 字以内。只输出这一句。",
        "judge": (
            "严格只输出 JSON：{\"score\":0-100,"
            "\"good\":[\"最多2条，哪一步论证真的有效\"],"
            "\"leaks\":[\"最多2条，哪里被原立场反打\"],"
            "\"one_line\":\"一句话总评，30字以内\"}\n"
            "评的维度：有没有正面回应原立场、有没有偷换概念、有没有只情绪不论证。"
        ),
    },
    "title": {
        "name": "标题训练",
        "sys": "你是标题编辑。用户会拿到一篇稿，要写 5 个标题。你按点击欲和信息准确度打分。",
        "ask": "给一段 200-300 字的中文稿（真实观点、有具体信息），只输出稿子本身。",
        "judge": (
            "严格只输出 JSON：{\"score\":0-100,"
            "\"per_title\":[{\"t\":\"他的标题\",\"s\":0-100,\"why\":\"一句评\"}],"
            "\"best\":\"最该用的那个\","
            "\"one_line\":\"一句话总评，30字以内\"}\n"
            "标题超过 20 字要扣分；只喊口号不给信息的要扣分。"
        ),
    },
    "summary": {
        "name": "摘要压缩",
        "sys": "你是编辑。用户要把 2000 字压成 100 字。你要比对要点保留率。",
        "ask": "给一段 600-900 字的中文长文（有 4-6 个要点），只输出正文。",
        "judge": (
            "严格只输出 JSON：{\"score\":0-100,"
            "\"kept\":[\"保留住的核心要点\"],"
            "\"lost\":[\"压掉的关键信息\"],"
            "\"one_line\":\"一句话总评，30字以内\"}\n"
            "超过 120 字直接扣到 60 分以下。"
        ),
    },
    "question": {
        "name": "提问训练",
        "sys": "你是提问教练。用户拿到一个话题，要列 10 个问题。你要判断哪些是真问题。",
        "ask": "给一个适合深挖的话题，一句话，20 字以内。只输出这一句。",
        "judge": (
            "严格只输出 JSON：{\"score\":0-100,"
            "\"real\":[\"他提的真问题\"],"
            "\"fake\":[\"假问题：能百度到的、绕圈子的、回答不了的\"],"
            "\"one_line\":\"一句话总评，30字以内\"}\n"
            "真问题 = 能逼对方给出具体信息或取舍的问题。"
        ),
    },
    "analogy": {
        "name": "类比训练",
        "sys": "你是表达教练。用户要把一个专业概念讲给完全外行的人听。你要评他的类比。",
        "ask": "给一个专业概念（商业/技术/心理皆可），一句话。只输出这个概念名和一句解释。",
        "judge": (
            "严格只输出 JSON：{\"score\":0-100,"
            "\"works\":[\"类比里成立的部分\"],"
            "\"breaks\":[\"类比失效的地方\"],"
            "\"one_line\":\"一句话总评，30字以内\"}\n"
            "评的维度：外行能不能听懂、类比有没有失真、有没有偷懒用术语。"
        ),
    },
}


def api_train_prompt(kind):
    """出题"""
    cfg = TRAIN_CFG.get(kind)
    if not cfg:
        return {"ok": False, "error": "没有这个训练"}
    out, err = _gw_chat("你是训练出题助手，只输出题目本身，不要任何解释和前后缀。",
                        cfg["ask"], max_tokens=800)
    if err:
        return {"ok": False, "error": "出不了题：" + err}
    return {"ok": True, "task": (out or "").strip(), "name": cfg["name"]}


def api_train_judge(kind, task, answer):
    """评你的回答"""
    cfg = TRAIN_CFG.get(kind)
    if not cfg:
        return {"ok": False, "error": "没有这个训练"}
    answer = (answer or "").strip()
    if len(answer) < 10:
        return {"ok": False, "error": "太短了，多说几句"}
    prompt = ("【题目】\n%s\n\n【他的回答】\n%s\n\n%s"
              % ((task or "")[:1500], answer[:3000], cfg["judge"]))
    out, err = _gw_chat(cfg["sys"], prompt, max_tokens=1600)
    if err:
        return {"ok": False, "error": "评不了：" + err}
    obj = _parse_json(out)
    if not obj:
        return {"ok": False, "error": "评语读不出来"}
    return {"ok": True, "result": obj, "name": cfg["name"]}

def api_book_cards(verdict=None, limit=60, q=None):
    """书卡列表"""
    import json as _j
    c = conn()
    try:
        sql = ("select k.book_id, k.gist, k.insights, k.for_who, k.solves, "
               "k.verdict, k.why, b.title, b.author, b.pages, b.category "
               "from book_card k join books b on b.id=k.book_id ")
        args = []
        where = []
        if verdict:
            where.append("k.verdict=?")
            args.append(verdict)
        if q:
            where.append("(instr(b.title,?)>0 or instr(k.gist,?)>0)")
            args += [q, q]
        if where:
            sql += "where " + " and ".join(where) + " "
        sql += "order by case k.verdict when '精读' then 0 when '翻翻' then 1 else 2 end, b.title limit ?"
        args.append(limit)
        rows = c.execute(sql, args).fetchall()
        out = []
        for r in rows:
            ins = []
            try:
                ins = _j.loads(r["insights"] or "[]")
            except Exception:
                pass
            out.append({"id": r["book_id"], "title": r["title"], "author": r["author"] or "",
                        "pages": r["pages"] or 0, "cat": r["category"] or "",
                        "gist": r["gist"] or "", "insights": ins,
                        "forWho": r["for_who"] or "", "solves": r["solves"] or "",
                        "verdict": r["verdict"] or "", "why": r["why"] or ""})
        # 统计
        stat = {}
        for r in c.execute("select coalesce(verdict,'?') v, count(*) n from book_card group by v"):
            stat[r["v"]] = r["n"]
        total = c.execute("select count(*) from book_card").fetchone()[0]
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True, "total": total, "stat": stat, "items": out}

# ================= 在家训练打卡 =================
TRAIN_WEEK = {
    0: {"name": "推 + 腿", "focus": "胸、肩、大腿",
        "items": [
            {"k": "俯卧撑", "s": "3 组，每组做到差 1-2 个做不动", "n": "做不到标准就跪姿，或手撑桌沿"},
            {"k": "深蹲", "s": "3 组 × 15 次", "n": "下 3 秒上 1 秒，慢比快有效"},
            {"k": "臀桥", "s": "3 组 × 20 次", "n": "顶到最高停 2 秒"},
            {"k": "平板支撑", "s": "2 组，撑到发抖", "n": ""},
        ]},
    1: {"name": "休息", "focus": "让肌肉长", "items": []},
    2: {"name": "拉 + 核心", "focus": "背、腹",
        "items": [
            {"k": "桌下划船", "s": "3 组 × 8-12 次", "n": "躺在结实桌子下，抓桌沿把身体拉上去"},
            {"k": "俯卧撑", "s": "2 组", "n": "保持上肢频率"},
            {"k": "平板支撑", "s": "3 组，撑到发抖", "n": ""},
            {"k": "侧平板", "s": "2 组 × 每侧 30 秒", "n": ""},
        ]},
    3: {"name": "休息", "focus": "让肌肉长", "items": []},
    4: {"name": "全身", "focus": "腿、臀、胸",
        "items": [
            {"k": "保加利亚分腿蹲", "s": "3 组 × 10 次/腿", "n": "后脚搭椅子上，前腿单腿蹲"},
            {"k": "俯卧撑", "s": "3 组", "n": ""},
            {"k": "桌下划船", "s": "3 组 × 8-12 次", "n": ""},
            {"k": "臀桥", "s": "3 组 × 20 次", "n": ""},
        ]},
    5: {"name": "棒铃 HIIT", "focus": "心肺 + 燃脂",
        "items": [
            {"k": "棒铃摆动", "s": "20 秒全力 + 40 秒休息，8 轮", "n": "共 8 分钟，心率要冲到 160 以上"},
            {"k": "拉伸", "s": "5 分钟", "n": "腿后侧、胸、肩"},
        ]},
    6: {"name": "完全休息", "focus": "什么都不做", "items": []},
}

TRAIN_DAILY = [
    "蛋白质吃到 115g，今天吃够了吗",
    "睡够 7 小时，固定时间睡",
    "喝够 2 升水",
]


def api_train_week():
    """这周的训练计划 + 今天该做什么 + 连续打卡"""
    import time as _tm
    now = _tm.localtime()
    today = now.tm_wday
    c = conn()
    try:
        done_today = set()
        for r in c.execute("select item from train_log where day=?",
                           (_tm.strftime("%Y-%m-%d"),)):
            done_today.add(r["item"])
        # 连续打卡天数（从今天往前数，每天至少完成 1 项）
        streak = 0
        for i in range(0, 400):
            d = _tm.strftime("%Y-%m-%d", _tm.localtime(_tm.time() - i * 86400))
            n = c.execute("select count(*) from train_log where day=?", (d,)).fetchone()[0]
            if n > 0:
                streak += 1
            elif i > 0:
                break
        # 最近 14 天记录
        hist = []
        for i in range(13, -1, -1):
            d = _tm.strftime("%Y-%m-%d", _tm.localtime(_tm.time() - i * 86400))
            n = c.execute("select count(*) from train_log where day=?", (d,)).fetchone()[0]
            hist.append({"d": d[5:], "n": n})
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()

    wk = []
    for i in range(7):
        v = TRAIN_WEEK[i]
        wk.append({"d": ["一", "二", "三", "四", "五", "六", "日"][i],
                   "name": v["name"], "focus": v["focus"],
                   "items": v["items"], "today": i == today})
    t = TRAIN_WEEK[today]
    return {"ok": True, "today": today, "todayName": t["name"], "todayFocus": t["focus"],
            "todayItems": t["items"], "done": list(done_today),
            "week": wk, "streak": streak, "hist": hist, "daily": TRAIN_DAILY}


def api_train_check(item, date=None):
    """打勾 / 取消"""
    import time as _tm
    d = date or _tm.strftime("%Y-%m-%d")
    c = conn()
    try:
        has = c.execute("select 1 from train_log where day=? and item=?", (d, item)).fetchone()
        if has:
            c.execute("delete from train_log where day=? and item=?", (d, item))
            act = "undo"
        else:
            c.execute("insert into train_log(day, item, at) values(?,?,?)",
                      (d, item, _tm.strftime("%Y-%m-%d %H:%M:%S")))
            act = "do"
        c.commit()
    except Exception as e:
        c.close()
        return {"ok": False, "error": str(e)}
    c.close()
    return {"ok": True, "act": act}

# ================= 动作教程 =================
EX_GUIDE = {
    "俯卧撑": {
        "target": "3 组，每组做到差 1-2 个就做不动",
        "steps": [
            "趴下，双手撑地，手比肩略宽一点，手指朝前",
            "身体从头到脚成一条直线，别塌腰别撅屁股",
            "吸气，手肘弯到 90 度左右，胸口快碰到地面（不用真碰）",
            "呼气，把他推起来，推到手臂伸直但不锁死",
        ],
        "errors": [
            "屁股撅起来（省力，但练不到胸）",
            "腰塌下去（伤腰）",
            "只下去一半（要下到肘 90 度）",
        ],
        "easier": "做不到标准就跪着做（膝盖着地）；再不行就手撑桌沿或墙，撑得越高越轻松。从「能做完 8 个」的高度开始，两周降一次。",
    },
    "深蹲": {
        "target": "3 组 × 15 次，下 3 秒上 1 秒",
        "steps": [
            "双脚与肩同宽，脚尖稍微朝外",
            "双手往前平举保持平衡（有棒铃就抱在胸前）",
            "屁股往后坐，像要坐到椅子上，膝盖跟着弯",
            "蹲到大腿和地面平行（或更低），停一下",
            "脚后跟发力站起来，胸口保持抬起",
        ],
        "errors": [
            "膝盖往里扣（要跟着脚尖方向）",
            "脚后跟离地（说明小腿太紧，先拉伸）",
            "上身往前趴太多（背要直）",
        ],
        "easier": "蹲不到底就先蹲一半，或者屁股后面放把椅子，碰一下就起来。腰不好就扶着门框做。",
    },
    "臀桥": {
        "target": "3 组 × 20 次，顶到最高停 2 秒",
        "steps": [
            "躺地上，膝盖弯起来，双脚踩地，脚跟离屁股约一个手掌",
            "双手放身体两侧，掌心朝下",
            "屁股发力往上顶，顶到大腿和身体成一条斜线",
            "在最高点停 2 秒，感觉屁股夹紧",
            "慢慢放下来，不要一下砸地",
        ],
        "errors": [
            "用腰发力顶（应该是屁股发力，腰不酸才对）",
            "顶得太高，腰反弓（顶到大腿身体成直线就停）",
            "脚离屁股太远（越远越难，越近越轻松）",
        ],
        "easier": "单腿做更难，双腿做已经够了。觉得太轻松就在肚子上放个重物（一箱水、一摞书）。",
    },
    "平板支撑": {
        "target": "2-3 组，每组撑到身体开始抖",
        "steps": [
            "趴下，用手肘和前臂撑地，肘在肩膀正下方",
            "脚尖撑地，身体从头到脚成一条直线",
            "收腹，屁股夹紧，别让腰塌下去",
            "正常呼吸，别憋气",
        ],
        "errors": [
            "屁股翘起来（省力但没用）",
            "腰塌下去（伤腰，最危险）",
            "憋气（应该正常呼吸）",
        ],
        "easier": "撑不住就跪着用膝盖撑；或者手撑桌子（斜的平板）。先从 20 秒开始，每周加 5 秒。",
    },
    "桌下划船": {
        "target": "3 组 × 8-12 次",
        "steps": [
            "找一张结实的桌子（能承受你体重，别用玻璃的）",
            "躺在桌子下面，双手抓住桌沿，手比肩略宽",
            "身体绷直，脚跟着地，先把身体拉成一条直线（这是起始位）",
            "背部发力，把胸口往桌面拉，拉到胸口快碰桌底",
            "慢慢放下去，控制住不要掉",
        ],
        "errors": [
            "用手臂拉（应该是背发力，想象把手肘往身后夹）",
            "屁股先起来（身体要保持一条线）",
            "放下去太快（下放要慢，那是长肌肉的部分）",
        ],
        "easier": "身体越平越难。觉得太难就把脚往回收，让身体斜一点。没有结实桌子就用两条毛巾套在门把手上做。",
    },
    "保加利亚分腿蹲": {
        "target": "3 组 × 10 次/腿",
        "steps": [
            "背对椅子站，一只脚往后搭在椅子上（脚背朝下）",
            "前脚往前迈一大步，站稳",
            "身体垂直往下蹲，前腿蹲到大腿平行地面",
            "前脚发力站起来",
            "做完一条腿换另一条",
        ],
        "errors": [
            "前脚离椅子太近（越近越难，要往前站）",
            "身体往前趴（保持直上直下）",
            "前膝超过脚尖太多（会让膝盖压力大）",
        ],
        "easier": "这是最难受的动作。做不到就先做普通弓步蹲（不加椅子），或者扶着墙做。宁可少做几个，也别做成歪的。",
    },
    "侧平板": {
        "target": "2 组 × 每侧 30 秒",
        "steps": [
            "侧躺，用一侧前臂撑地，肘在肩膀正下方",
            "两脚叠起来（或前后错开更稳）",
            "把屁股顶起来，身体成一条直线",
            "另一只手叉腰或往上指",
        ],
        "errors": [
            "屁股往下掉（要顶起来）",
            "身体往前倾或往后倒（保持侧面朝上）",
        ],
        "easier": "撑不住就用膝盖撑地（屈膝侧平板）。先从 15 秒开始。",
    },
    "棒铃摆动": {
        "target": "20 秒全力 + 40 秒休息，8 轮共 8 分钟",
        "steps": [
            "双脚比肩略宽，双手握棒铃，握距与肩同宽",
            "屁股往后坐，把棒铃往两腿之间送（像开合跳的摆臂）",
            "屁股猛地往前顶，用这个力把棒铃甩到胸口高度",
            "手臂只是绳子，不要用肩膀往上抬",
            "让它自然荡回来，接着下一轮",
        ],
        "errors": [
            "用手臂抬（会伤肩，应该是屁股和髋部发力）",
            "蹲太深变成深蹲（是髋铰链，不是蹲）",
            "腰弓着（背要直，核心收紧）",
        ],
        "easier": "怕甩不好就先双手提棒铃做「罗马尼亚硬拉」，感受髋部发力。等动作顺了再加速。",
    },
}


def api_ex_guide(name):
    g = EX_GUIDE.get(name or "")
    if not g:
        return {"ok": False, "error": "没有这个动作的教程"}
    return {"ok": True, "name": name, "guide": g}

# ---------------- HTML ----------------

def html_page():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile_page.html")
    with open(p, encoding="utf-8") as f:
        return f.read()


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(b)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            # 除 ping 外一律要登录
            if u.path != "/api/ping" and _password() and not _authed(self):
                if u.path in ("/", "/index.html"):
                    return self._send(200, LOGIN_HTML, "text/html; charset=utf-8")
                return self._send(401, json.dumps({"ok": False, "error": "未登录"}, ensure_ascii=False))
            if u.path in ("/", "/index.html"):
                return self._send(200, html_page(), "text/html; charset=utf-8")
            if u.path == "/api/list":
                return self._send(200, json.dumps(api_list(int(q.get("limit", ["20"])[0])), ensure_ascii=False))
            if u.path == "/api/ideas":
                return self._send(200, json.dumps(api_ideas(), ensure_ascii=False))
            if u.path == "/api/stats":
                return self._send(200, json.dumps(api_stats(), ensure_ascii=False))
            if u.path == "/api/undo":
                return self._send(200, json.dumps(api_undo(), ensure_ascii=False))
            if u.path == "/api/library":
                return self._send(200, json.dumps(api_library_stats(), ensure_ascii=False))
            if u.path == "/api/capture":
                return self._send(200, json.dumps(api_capture_stats(), ensure_ascii=False))
            if u.path == "/api/topics":
                return self._send(200, json.dumps(api_topics(), ensure_ascii=False))
            if u.path == "/api/myviews":
                return self._send(200, json.dumps(api_myviews(), ensure_ascii=False))
            if u.path == "/api/myview":
                return self._send(200, json.dumps(api_view_one(q.get("id", [""])[0]), ensure_ascii=False))
            if u.path == "/api/match":
                return self._send(200, json.dumps(api_match_semantic(q.get("text", [""])[0]), ensure_ascii=False))
            if u.path == "/api/personas":
                return self._send(200, json.dumps(api_personas(), ensure_ascii=False))
            if u.path == "/api/roundtable":
                return self._send(200, json.dumps(api_roundtable(), ensure_ascii=False))
            if u.path == "/api/corpus":
                return self._send(200, json.dumps(api_corpus(), ensure_ascii=False))
            if u.path == "/api/draft_status":
                return self._send(200, json.dumps(api_draft_status(q.get("task", [""])[0]), ensure_ascii=False))
            if u.path == "/api/roundtable_status":
                return self._send(200, json.dumps(api_roundtable_status(q.get("task", [""])[0]), ensure_ascii=False))
            if u.path == "/api/roundtable_get":
                return self._send(200, json.dumps(api_roundtable_get(q.get("task", [""])[0]), ensure_ascii=False))
            if u.path == "/api/corpus_flags":
                return self._send(200, json.dumps(api_corpus_flags(), ensure_ascii=False))
            if u.path == "/api/speech_settings":
                return self._send(200, json.dumps(api_speech_settings_get(), ensure_ascii=False))
            if u.path == "/api/book_cards":
                return self._send(200, json.dumps(api_book_cards(q.get("verdict", [None])[0], int(q.get("limit", ["60"])[0]), q.get("q", [None])[0]), ensure_ascii=False))
            if u.path == "/api/train_week":
                _ensure_train_table()
                return self._send(200, json.dumps(api_train_week(), ensure_ascii=False))
            if u.path == "/api/train_check":
                _ensure_train_table()
                return self._send(200, json.dumps(api_train_check(body.get("item"), body.get("date")), ensure_ascii=False))
            if u.path == "/api/ex_guide":
                return self._send(200, json.dumps(api_ex_guide(q.get("n", [""])[0]), ensure_ascii=False))
            if u.path == "/api/ping":
                return self._send(200, json.dumps({"ok": True, "at": time.time()}))
            self._send(404, json.dumps({"ok": False, "error": "not found"}, ensure_ascii=False))
        except Exception as e:
            log("GET %s 出错: %s" % (self.path, e))
            self._send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))

    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("content-length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            body = {}
        try:
            if u.path == "/login":
                if str(body.get("p") or "").strip() == _password():
                    tok = _token()
                    self.send_response(200)
                    self.send_header("content-type", "application/json; charset=utf-8")
                    self.send_header("set-cookie",
                                     "%s=%s; Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax"
                                     % (COOKIE_NAME, tok))
                    _b = json.dumps({"ok": True}).encode("utf-8")
                    self.send_header("content-length", str(len(_b)))
                    self.end_headers()
                    self.wfile.write(_b)
                    return
                return self._send(200, json.dumps({"ok": False, "error": "密码不对"}, ensure_ascii=False))
            if _password() and not _authed(self):
                return self._send(401, json.dumps({"ok": False, "error": "未登录"}, ensure_ascii=False))
            if u.path == "/api/roundtable_next":
                return self._send(200, json.dumps(api_roundtable_next(body.get("id")), ensure_ascii=False))
            if u.path == "/api/roundtable_ask":
                return self._send(200, json.dumps(api_roundtable_ask(body.get("id"), body.get("pid"), body.get("q")), ensure_ascii=False))
            if u.path == "/api/roundtable_del":
                return self._send(200, json.dumps(api_roundtable_del(body.get("id")), ensure_ascii=False))
            if u.path == "/api/persona_chat":
                return self._send(200, json.dumps(api_persona_chat(body.get("id"), body.get("q")), ensure_ascii=False))
            if u.path == "/api/roundtable_open":
                return self._send(200, json.dumps(api_roundtable_open(body.get("q"), body.get("ids")), ensure_ascii=False))
            if u.path == "/api/corpus_add":
                return self._send(200, json.dumps(api_corpus_add(body.get("id"), bool(body.get("on", True))), ensure_ascii=False))
            if u.path == "/api/view_replace":
                return self._send(200, json.dumps(api_view_replace(body.get("id"), body.get("content")), ensure_ascii=False))
            if u.path == "/api/view_polish":
                return self._send(200, json.dumps(api_view_polish(body.get("id")), ensure_ascii=False))
            if u.path == "/api/view_review":
                return self._send(200, json.dumps(api_view_review(body.get("id")), ensure_ascii=False))
            if u.path == "/api/view_del":
                return self._send(200, json.dumps(api_view_del(body.get("id")), ensure_ascii=False))
            if u.path == "/api/speech_settings_save":
                return self._send(200, json.dumps(api_speech_settings_save(body), ensure_ascii=False))
            if u.path == "/api/speech_custom":
                return self._send(200, json.dumps(api_speech_custom_hits(body.get("text")), ensure_ascii=False))
            if u.path == "/api/train_prompt":
                return self._send(200, json.dumps(api_train_prompt(body.get("kind")), ensure_ascii=False))
            if u.path == "/api/train_judge":
                return self._send(200, json.dumps(api_train_judge(body.get("kind"), body.get("task"), body.get("answer")), ensure_ascii=False))
            if u.path == "/api/speech_polish":
                return self._send(200, json.dumps(api_speech_polish(body.get("text")), ensure_ascii=False))
            if u.path == "/api/speech_toview":
                return self._send(200, json.dumps(api_myview_add(body.get("text"), body.get("title")), ensure_ascii=False))
            if u.path == "/api/speech_analyze":
                return self._send(200, json.dumps(api_speech_analyze(body.get("text")), ensure_ascii=False))
            if u.path == "/api/speech_tip":
                return self._send(200, json.dumps(api_speech_tip(body.get("text")), ensure_ascii=False))
            if u.path == "/api/speech_report":
                return self._send(200, json.dumps(api_speech_report(body.get("text"), int(body.get("filler") or 0), int(body.get("hedge") or 0), int(body.get("density") or 0)), ensure_ascii=False))
            if u.path == "/api/topic_status":
                return self._send(200, json.dumps(api_topic_status(body.get("id"), body.get("status")), ensure_ascii=False))
            if u.path == "/api/topic_del":
                return self._send(200, json.dumps(api_topic_del(body.get("id")), ensure_ascii=False))
            if u.path == "/api/draft":
                return self._send(200, json.dumps(api_draft_start(body.get("id"), bool(body.get("rewrite"))), ensure_ascii=False))
            if u.path == "/api/myview_add":
                return self._send(200, json.dumps(api_myview_add(body.get("content"), body.get("title")), ensure_ascii=False))
            if u.path == "/api/vote":
                r = api_vote(body.get("atomId"), body.get("verdict"), body.get("why"))
            elif u.path == "/api/idea":
                r = api_idea_add(body.get("content"))
            else:
                r = {"ok": False, "error": "not found"}
            self._send(200, json.dumps(r, ensure_ascii=False))
        except Exception as e:
            log("POST %s 出错: %s" % (self.path, e))
            self._send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))


# 互斥体句柄必须存全局，否则被 GC 回收后单例失效
_MUTEX = None


def main():
    # 单例：Windows 命名互斥体
    # 注意：ctypes 必须用 use_last_error=True + get_last_error()，
    # 直接 k32.GetLastError() 拿到的是"调用前"的残留错误码，会误判。
    global _MUTEX
    try:
        import ctypes as _ct
        _k32 = _ct.WinDLL("kernel32", use_last_error=True)
        _MUTEX = _k32.CreateMutexW(None, False, "Local\\DSH_Pocket_8788")
        if _ct.get_last_error() == 183:   # ERROR_ALREADY_EXISTS
            log("已有实例在跑，本进程退出")
            return
    except Exception as e:
        log("互斥体检查失败（继续启动）: %s" % e)
        _MUTEX = None
    log("=== 口袋服务启动 :%d ===" % PORT)
    STARTUP_TRAIN = True
    try:
        _ensure_train_table()
    except Exception:
        pass
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    srv.serve_forever()


if __name__ == "__main__":
    main()
