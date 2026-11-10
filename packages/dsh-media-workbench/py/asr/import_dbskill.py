# -*- coding: utf-8 -*-
"""把 dbskill 的原子库与推文集导入工作台数据库。

数据模型（两层）：
  atoms  = 原子本体（knowledge / original / url / date / topics / skills / type / confidence）
           + 用途层 usage（hook 钩子 / evidence 论据 / opinion 观点 / ending 收尾），初始为空
  posts  = 推文集里的完整条目（推文/引用/文章）
"""
import json
import re
import os
import re
import sqlite3
import sys
from datetime import datetime

SRC = r"E:\tools\tmp-repos\dbskill"
DB = r"E:\desktop\media\workbench.db"
ATOMS = os.path.join(SRC, "知识库", "原子库")
BOOK = os.path.join(SRC, "books", "dontbesilent-开源推文集.md")

SCHEMA = """
CREATE TABLE IF NOT EXISTS atoms (
  id          TEXT PRIMARY KEY,
  author      TEXT NOT NULL DEFAULT 'dontbesilent',
  knowledge   TEXT NOT NULL,
  original    TEXT,
  url         TEXT,
  date        TEXT,
  topics      TEXT,          -- JSON array
  skills      TEXT,          -- JSON array
  type        TEXT,
  confidence  TEXT,
  usage       TEXT DEFAULT '[]',   -- JSON array: hook/evidence/opinion/ending
  created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_atoms_date  ON atoms(date);
CREATE INDEX IF NOT EXISTS idx_atoms_type  ON atoms(type);

CREATE TABLE IF NOT EXISTS posts (
  id          TEXT PRIMARY KEY,
  author      TEXT NOT NULL DEFAULT 'dontbesilent',
  date        TEXT,
  kind        TEXT,          -- 原创/引用/文章/转发
  text        TEXT NOT NULL,
  url         TEXT,
  created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_date ON posts(date);

CREATE TABLE IF NOT EXISTS meta (
  k TEXT PRIMARY KEY,
  v TEXT
);
"""



URL_RE = re.compile(r'(https?://\S+|www\.\S+)', re.I)
SHARE_RE = re.compile(r'(复制打开抖音|长按复制此条消息|打开抖音搜索|私信我要链接|统一回复一下|拍链接|付费咨询在这|主战场小红书|抢购链接|标记时点|夸克网盘)')

def is_junk_atom(text):
    """纯链接 / 分享广告 / 断句残片 → 不入库"""
    t = (text or "").strip()
    if not t:
        return True
    if SHARE_RE.search(t):
        return True
    if URL_RE.search(t):
        rest = URL_RE.sub("", t).strip()
        if len(rest) < 20:
            return True
    if len(t) < 12:
        return True
    if re.search(r'[：:，,；;、]$', t):
        return True
    return False

def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    con.commit()
    return con


def import_atoms(con):
    files = sorted(
        f for f in os.listdir(ATOMS) if f.startswith("atoms") and f.endswith(".jsonl")
    )
    total = 0
    skipped = 0
    now = datetime.now().isoformat(timespec="seconds")
    cur = con.cursor()
    for fn in files:
        path = os.path.join(ATOMS, fn)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    a = json.loads(line)
                except Exception:
                    skipped += 1
                    continue
                aid = a.get("id")
                know = (a.get("knowledge") or "").strip()
                if not aid or not know:
                    skipped += 1
                    continue
                if is_junk_atom(know):
                    skipped += 1
                    continue
                cur.execute(
                    """INSERT OR REPLACE INTO atoms
                       (id, knowledge, original, url, date, topics, skills, type, confidence, usage, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        aid,
                        know,
                        a.get("original"),
                        a.get("url"),
                        a.get("date"),
                        json.dumps(a.get("topics", []), ensure_ascii=False),
                        json.dumps(a.get("skills", []), ensure_ascii=False),
                        a.get("type"),
                        a.get("confidence"),
                        "[]",
                        now,
                    ),
                )
                total += 1
        print(f"  {fn}: done, cumulative={total}")
    con.commit()
    return total, skipped


def parse_book(con):
    """推文集格式：
    ## 2026-07-19 · 引用
    > 正文（多行引用）
    原帖：[url](url)
    """
    if not os.path.exists(BOOK):
        return 0
    with open(BOOK, "r", encoding="utf-8") as f:
        raw = f.read()

    blocks = re.split(r"\n## ", raw)
    cur = con.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    n = 0
    for b in blocks[1:]:
        head, _, body = b.partition("\n")
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s*[·\-]\s*(.+)", head.strip())
        if not m:
            continue
        date, kind = m.group(1), m.group(2).strip()
        # 正文：以 > 开头的行
        lines = []
        url = None
        for ln in body.splitlines():
            s = ln.strip()
            if s.startswith(">"):
                lines.append(s.lstrip("> ").rstrip())
            elif s.startswith("原帖") or s.startswith("链接"):
                mu = re.search(r"\((https?://[^)]+)\)", s)
                if mu:
                    url = mu.group(1)
        text = "\n".join(lines).strip()
        if len(text) < 10:
            continue
        pid = f"post_{date}_{n:04d}"
        cur.execute(
            "INSERT OR REPLACE INTO posts (id, date, kind, text, url, created_at) VALUES (?,?,?,?,?,?)",
            (pid, date, kind, text, url, now),
        )
        n += 1
    con.commit()
    return n


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print(f"[db] {DB}")
    con = init_db()

    print("[import] atoms ...")
    na, sk = import_atoms(con)
    print(f"[import] atoms done: {na} inserted, {sk} skipped")

    print("[import] posts ...")
    np = parse_book(con)
    print(f"[import] posts done: {np}")

    # 统计
    cur = con.cursor()
    def q(sql):
        return cur.execute(sql).fetchone()[0]
    stats = {
        "atoms": q("SELECT COUNT(*) FROM atoms"),
        "posts": q("SELECT COUNT(*) FROM posts"),
        "with_url": q("SELECT COUNT(*) FROM atoms WHERE url IS NOT NULL AND url<>''"),
        "with_topics": q("SELECT COUNT(*) FROM atoms WHERE topics<>'[]'"),
    }
    print("[stats]", json.dumps(stats, ensure_ascii=False))

    # type 分布
    print("[type 分布]")
    for t, c in cur.execute("SELECT type, COUNT(*) FROM atoms GROUP BY type ORDER BY 2 DESC LIMIT 12"):
        print(f"  {t}: {c}")

    # 高频 topic
    print("[高频 topic Top 15]")
    from collections import Counter
    cnt = Counter()
    for (tj,) in cur.execute("SELECT topics FROM atoms"):
        try:
            for t in json.loads(tj or "[]"):
                cnt[t] += 1
        except Exception:
            pass
    for t, c in cnt.most_common(15):
        print(f"  {t}: {c}")

    print("[sample] 前 3 条原子:")
    for row in cur.execute("SELECT id, knowledge, type, confidence FROM atoms LIMIT 3"):
        print("  ", row[0], "|", row[1][:60], "|", row[2], "|", row[3])

    con.close()


if __name__ == "__main__":
    main()
