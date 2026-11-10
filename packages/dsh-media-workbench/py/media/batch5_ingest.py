# -*- coding: utf-8 -*-
"""① 入库 9 本新下载的 epub ② 删掉 4 本扫描 PDF 所在的抽坏书（全部 44 本无替代版的抽坏书）"""
import hashlib, json, os, re, sqlite3, sys, time, zipfile
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\desktop\media\workbench.db"
NEW = r"E:\wengao_新书"
BAK = r"E:\desktop\书库盘点\_清理备份_20261107_批5"
os.makedirs(BAK, exist_ok=True)

NEW_BOOKS = [
    ("走进我的交易室.epub", "走进我的交易室", "埃尔德", "商业与变现", "投资理财"),
    ("游戏改变世界.epub", "游戏改变世界", "简·麦戈尼格尔", "心理与人性", "习惯养成"),
    ("短线交易大师.epub", "短线交易大师——工具和策略", "", "商业与变现", "投资理财"),
    ("异类：不一样的成功启示录.epub", "异类：不一样的成功启示录", "马尔科姆·格拉德威尔", "心理与人性", "自我认知"),
    ("穿布鞋的马云.epub", "穿布鞋的马云", "", "商业与变现", "商业史案例"),
    ("炒股的智慧.epub", "炒股的智慧", "陈江挺", "商业与变现", "投资理财"),
    ("设计中的设计.epub", "设计中的设计", "原研哉", "内容创作", "视觉与设计"),
    ("数字化定量分析.epub", "数字化定量分析", "", "商业与变现", "投资理财"),
    ("传统企业如何做电商及微电商.epub", "传统企业如何做电商及微电商", "", "商业与变现", "流量获取"),
]


def epub_text(path):
    parts = []
    with zipfile.ZipFile(path) as z:
        for n in sorted(z.namelist()):
            if not n.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            raw = z.read(n).decode("utf-8", "ignore")
            raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S | re.I)
            raw = re.sub(r"<br\s*/?>|</p>|</div>|</h\d>", "\n", raw, flags=re.I)
            raw = re.sub(r"<[^>]+>", "", raw)
            raw = raw.replace("&nbsp;", " ")
            parts.append(raw)
    return "\n".join(parts)


def ingest(txt, title, author, topic, sub):
    txt = re.sub(r"\n{3,}", "\n\n", txt.replace("\r\n", "\n"))
    total = len(txt)
    paras = [p.strip() for p in txt.split("\n") if p.strip()]
    chunks, buf, head = [], [], ""
    for p in paras:
        if len(buf) == 0 and len(p) < 60:
            head = p[:60]
        buf.append(p)
        if sum(len(x) for x in buf) >= 2000:
            chunks.append((head, "\n".join(buf)))
            buf, head = [], ""
    if buf:
        chunks.append((head, "\n".join(buf)))
    bid = "book_" + hashlib.md5((title + str(total)).encode()).hexdigest()[:12]
    c = sqlite3.connect(DB)
    for tb in ("book_chunks", "chunks_fts", "book_labels", "books"):
        col = "book_id" if tb != "books" else "id"
        c.execute("delete from %s where %s=?" % (tb, col), (bid,))
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    pages = max(1, total // 1000)
    c.execute("""insert into books(id,title,author,source_path,pages,ocr_state,quality,summary,doable,category,created_at)
                 values(?,?,?,?,?,?,?,?,?,?,?)""",
              (bid, title, author, os.path.join(NEW, title), pages, "done", "", "", "", "", now))
    for i, (hd, content) in enumerate(chunks):
        c.execute("insert into book_chunks(id,book_id,page_from,page_to,heading,content,chars,created_at)"
                  " values(?,?,?,?,?,?,?,?)",
                  ("%s_c%04d" % (bid, i), bid, i + 1, i + 1, hd[:80], content, len(content), now))
        c.execute("insert into chunks_fts(tok, content, book_id, page_from) values(?,?,?,?)",
                  (" ".join(content), content, bid, i + 1))
    c.execute("insert or replace into book_labels values(?,?,?,?,?,?,?)",
              (bid, topic, "", sub, sub, 1.0, now))
    c.commit()
    c.close()
    return bid, total, len(chunks)


print("=== ① 入库新书 ===")
ok = 0
for fn, title, author, topic, sub in NEW_BOOKS:
    p = os.path.join(NEW, fn)
    if not os.path.exists(p):
        print("  跳过（文件不存在）", fn)
        continue
    t = epub_text(p)
    if len(t) < 30000:
        print("  跳过（提取字数太少 %d）%s" % (len(t), fn))
        continue
    bid, n, cnt = ingest(t, title, author, topic, sub)
    print("  ✔ %s | %d 字 %d 块" % (title[:28], n, cnt))
    ok += 1
print("入库 %d 本" % ok)

# ===== ② 删抽坏书（除已补回的）=====
print("\n=== ② 删抽坏书 ===")
c = sqlite3.connect(DB)
q = lambda s, p=(): c.execute(s, p).fetchall()
replaced = {t for _, t, _, _, _ in NEW_BOOKS}
broken = q("""select qq.book_id, b.title from book_quality qq join books b on b.id=qq.book_id
              where qq.intact=0""")
keep, dele = [], []
for bid, t in broken:
    if any(r[:6] in (t or "") or (t or "")[:6] in r for r in replaced):
        keep.append((bid, t))
    else:
        dele.append((bid, t))
print("抽坏仍留库 %d 本（已补新版）：%s" % (len(keep), [t[:20] for _, t in keep]))
print("删除 %d 本无替代版的抽坏书" % len(dele))

exp = {}
for bid, t in dele:
    exp[bid] = {"title": t, "chunks": [[p, x] for p, x in q(
        "select page_from, content from book_chunks where book_id=?", (bid,))]}
json.dump(exp, open(os.path.join(BAK, "待删抽坏书正文.json"), "w", encoding="utf-8"), ensure_ascii=False)

ids = [b for b, _ in dele]
if ids:
    ph = ",".join("?" * len(ids))
    tabs = [r[0] for r in q("select name from sqlite_master where type='table'")
            if any(col[1] == "book_id" for col in c.execute("pragma table_info(%s)" % r[0]))]
    for tb in tabs:
        c.execute("delete from %s where book_id in (%s)" % (tb, ph), ids)
    c.execute("delete from books where id in (%s)" % ph, ids)
    c.commit()

print("\n现库：%d 本 / %d 块 / %d 字" % (
    q("select count(*) from books")[0][0], q("select count(*) from book_chunks")[0][0],
    q("select sum(length(content)) from book_chunks")[0][0]))
c.close()
