# -*- coding: utf-8 -*-
"""手机端选题池：点标题就地展开 + 四个按钮（AI写/我来写/改状态/删）。

AI 写的 prompt 照搬桌面端 DRAFT_SYSTEM，走本机 V3.2 网关。
"""
import re

H = r"E:\desktop\media\mobile_page.html"
S = r"E:\desktop\media\mobile_server.py"

# ============ 后端：加 /api/draft /api/topic_status /api/topic_del ============
srv = open(S, encoding="utf-8").read()

BACKEND = '''

DRAFT_SYSTEM = """你要替一个做知识类内容的自媒体博主，把一条选题写成可以直接开拍的口播稿。

铁律：
- 只用【原始素材】里的事实和观点。素材里没有的数字、案例、经历，一个都不许加。
- 素材不足以支撑这条选题，就直说「素材不够，这条写不了」并说明缺什么，不要硬写。
- 用大白话，第一人称，像在跟同行的朋友讲话。
- 不要「值得注意的是」「意义重大」这类空话，不要「点赞关注」结尾。
"""


def _gateway_chat(system, prompt, max_tokens=2600):
    import json as _j
    import urllib.request as _u
    key = ""
    try:
        key = open(r"E:\\DSH-data\\.dsh\\openai-gateway\\api-key", encoding="utf-8").read().strip()
    except Exception:
        return None, "读不到网关 key"
    body = _j.dumps({
        "model": "siliconflow/deepseek-ai/DeepSeek-V3.2",
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "temperature": 0.75,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    try:
        req = _u.Request("http://127.0.0.1:8326/v1/chat/completions", data=body,
                         headers={"content-type": "application/json",
                                  "authorization": "Bearer " + key})
        with _u.urlopen(req, timeout=240) as r:
            j = _j.loads(r.read().decode("utf-8"))
        return (j["choices"][0]["message"]["content"] or "").strip(), None
    except Exception as e:
        return None, str(e)[-200:]


def _src_text(c, kind, ref):
    """按选题的来源取原始素材正文"""
    if not ref:
        return None
    try:
        if kind in ("atom", "atoms"):
            r = c.execute("select knowledge from atoms where id=?", (ref,)).fetchone()
            return r[0] if r else None
        if kind in ("post", "posts"):
            r = c.execute("select text from posts where id=?", (ref,)).fetchone()
            return r[0] if r else None
        if kind in ("live", "live_segment"):
            r = c.execute("select text from live_segments where id=?", (ref,)).fetchone()
            return r[0] if r else None
        # 兜底：挨个表试
        for tb, col in (("atoms", "knowledge"), ("posts", "text"), ("live_segments", "text")):
            try:
                r = c.execute("select %s from %s where id=?" % (col, tb), (ref,)).fetchone()
                if r:
                    return r[0]
            except Exception:
                pass
    except Exception:
        pass
    return None


def api_draft(topic_id, rewrite=False):
    """AI 写：给一条选题生成口播稿，结果缓存在 draft 里"""
    import json as _j
    c = conn()
    r = c.execute("select * from pool_topics where id=?", (topic_id,)).fetchone()
    if not r:
        c.close()
        return {"ok": False, "error": "找不到这条选题"}
    t = dict(r)
    # 有缓存直接给
    cached = t.get("hook_draft") or ""
    if cached and not rewrite:
        c.close()
        return {"ok": True, "cached": True, "text": cached}
    src = _src_text(c, str(t.get("source_kind") or ""), str(t.get("source_ref") or ""))
    if not src:
        c.close()
        return {"ok": False, "error": "取不到原始素材，这条写不了"}
    prompt = ("选题：%s\\n切入角度：%s\\n开头钩子：%s\\n\\n【原始素材】\\n%s"
              % (t.get("title") or "", t.get("angle") or "", t.get("hook") or "",
                 str(src)[:4000]))
    text, err = _gateway_chat(DRAFT_SYSTEM, prompt)
    c.close()
    if err:
        return {"ok": False, "error": "写不出来：" + err}
    if not text:
        return {"ok": False, "error": "AI 返回空"}
    # 缓存进 extra 字段（不动原表结构）
    try:
        c2 = conn()
        import json as _jj
        ex = {}
        try:
            ex = _jj.loads(c2.execute("select coalesce(extra,'') from pool_topics where id=?",
                                      (topic_id,)).fetchone()[0] or "{}")
        except Exception:
            ex = {}
        ex["draft"] = text
        c2.execute("update pool_topics set extra=? where id=?",
                   (_jj.dumps(ex, ensure_ascii=False), topic_id))
        c2.commit()
        c2.close()
    except Exception:
        pass
    return {"ok": True, "text": text}


def api_topic_status(topic_id, status):
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


'''

anchor = "# ---------------- HTML ----------------"
if anchor in srv:
    srv = srv.replace(anchor, BACKEND.strip("\n") + "\n\n" + anchor, 1)
    print("后端函数已插入")

ROUTES = '''            if u.path == "/api/topic_status":
                return self._send(200, json.dumps(api_topic_status(body.get("id"), body.get("status")), ensure_ascii=False))
            if u.path == "/api/topic_del":
                return self._send(200, json.dumps(api_topic_del(body.get("id")), ensure_ascii=False))
            if u.path == "/api/draft":
                return self._send(200, json.dumps(api_draft(body.get("id"), bool(body.get("rewrite"))), ensure_ascii=False))
'''
# 放进 POST 分支
a = '''            if u.path == "/api/vote":'''
if a in srv:
    srv = srv.replace(a, ROUTES + a, 1)
    print("POST 路由已插入")

open(S + ".bak-draft", "wb").write(open(S, "rb").read())
open(S, "wb").write(srv.encode("utf-8"))

# ============ 前端：就地展开 + 四按钮 ============
h = open(H, encoding="utf-8").read()

OLD = '''function loadTopics() {
  api('/api/topics?limit=40').then(function (j) {
    var box = document.getElementById('topicsList');
    if (!j.ok) { box.innerHTML = '<div class="empty">读不到</div>'; return; }'''
NEW = '''var tOpen = null, tDraft = {};

function loadTopics() {
  api('/api/topics?limit=40').then(function (j) {
    var box = document.getElementById('topicsList');
    if (!j.ok) { box.innerHTML = '<div class="empty">读不到</div>'; return; }
    window.__topics = j.items || [];'''
if OLD in h:
    h = h.replace(OLD, NEW, 1)
    print("前端 loadTopics 头已改")

# 列表项改成按钮 + 就地展开
OLD2 = '''      return '<div class="litem">'
        + '<div class="lrow"><div class="lt">' + esc(it.title) + '</div>'
        + '<div class="lscore">' + lv + sc + '</div></div>'
        + (it.hook ? '<div class="ld">' + esc(it.hook) + '</div>' : '')
        + (it.note ? '<div class="ld">' + esc(it.note) + '</div>' : '')
        + (dims ? '<div class="ldim">' + dims + '</div>' : '')
        + (meta.length ? '<div class="ld">' + meta.join(' · ') + '</div>' : '')
        + '</div>';'''
NEW2 = '''      var open = (tOpen === it.id);
      var block = '<div class="lb"><div class="lrow"><div class="lt">' + esc(it.title) + '</div>'
        + '<div class="lscore">' + lv + sc + '</div></div>'
        + (it.hook ? '<div class="ld">' + esc(it.hook) + '</div>' : '')
        + (open && it.note ? '<div class="ld">角度：' + esc(it.note) + '</div>' : '')
        + (open && dims ? '<div class="ldim">' + dims + '</div>' : '')
        + (open && meta.length ? '<div class="ld">' + meta.join(' · ') + '</div>' : '')
        + (open ? actsHtml(it) : '')
        + '</div>';
      return '<div class="litem' + (open ? ' op' : '') + '" data-id="' + it.id + '">' + block + '</div>';'''
if OLD2 in h:
    h = h.replace(OLD2, NEW2, 1)
    print("列表项已改成就地展开")

# 加按钮 HTML 生成 + 交互
OLD3 = "function loadMyViews() {"
NEW3 = '''function actsHtml(it) {
  var d = tDraft[it.id];
  var st = it.status || 'idea';
  var a = '<div class="acts">'
    + '<button class="sb gold" data-act="ai" data-id="' + it.id + '">'
    + (d && d.text ? '收起' : 'AI 写') + '</button>'
    + '<button class="sb" data-act="mine" data-id="' + it.id + '">我来写</button>'
    + '<button class="sb" data-act="st" data-id="' + it.id + '">'
    + (st === 'writing' ? '标已发' : st === 'published' ? '退回想法' : '标在写') + '</button>'
    + '<button class="sb warn" data-act="del" data-id="' + it.id + '">删</button>'
    + '</div>';
  if (d && (d.loading || d.text || d.error)) {
    a += '<div class="draftbox">'
      + '<div class="dhead">AI 写的口播文案 · 只用原始素材里的事实</div>';
    if (d.loading) a += '<div class="dloading">正在读原始素材、起第一句…</div>';
    else if (d.error) a += '<div class="derr">写不出来：' + esc(d.error) + '</div>';
    else a += '<div class="dtext">' + esc(d.text) + '</div>';
    a += '</div>';
  }
  return a;
}

function topicTap(el) {
  var id = el.getAttribute('data-id');
  var act = el.getAttribute('data-act');
  if (!act) { tOpen = (tOpen === id ? null : id); renderTopics(); return; }
  if (act === 'ai') {
    var d = tDraft[id];
    if (d && d.text) { tDraft[id] = null; renderTopics(); return; }
    tDraft[id] = { loading: true };
    renderTopics();
    api('/api/draft', { method: 'POST', body: { id: id } }).then(function (j) {
      tDraft[id] = j.ok ? { text: j.text } : { error: j.error || '失败' };
      renderTopics();
    }).catch(function (e) { tDraft[id] = { error: e.message }; renderTopics(); });
    return;
  }
  if (act === 'mine') {
    setStat('我来写 · 手机端暂未开');
    return;
  }
  if (act === 'st') {
    var it = (window.__topics || []).filter(function (x) { return x.id === id; })[0] || {};
    var st = it.status || 'idea';
    var nxt = st === 'idea' ? 'writing' : st === 'writing' ? 'published' : 'idea';
    api('/api/topic_status', { method: 'POST', body: { id: id, status: nxt } }).then(function (j) {
      if (j.ok) { setStat('已改状态'); loadTopics(); } else setStat(j.error || '失败');
    });
    return;
  }
  if (act === 'del') {
    api('/api/topic_del', { method: 'POST', body: { id: id } }).then(function (j) {
      if (j.ok) { setStat('删掉了'); loadTopics(); } else setStat(j.error || '失败');
    });
    return;
  }
}

function renderTopics() {
  var box = document.getElementById('topicsList');
  if (!box.__html) return;
  box.innerHTML = box.__html;
  box.querySelectorAll('[data-act],[data-id]').forEach(function (e) {
    if (e.classList.contains('litem') || e.hasAttribute('data-act')) {
      e.onclick = function (ev) { ev.stopPropagation(); topicTap(e); };
    }
  });
}

function loadMyViews() {'''
if OLD3 in h:
    h = h.replace(OLD3, NEW3, 1)
    print("按钮逻辑已加")

open(H + ".bak-draft", "wb").write(open(H, "rb").read())
open(H, "wb").write(h.encode("utf-8"))
print("前端写盘")
