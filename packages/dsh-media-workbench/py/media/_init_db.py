#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化自媒体工作台主库：把表结构建好，空的，等采集往里写。

用法：
    python _init_db.py [数据根目录]
    python _init_db.py D:\\my-data

不带参数时用环境变量 DSH_MEDIA_DATA，再不行用 ~/dsh-media-data。
"""
import os
import sqlite3
import sys
from pathlib import Path

SCHEMA = """
-- 素材：书 / 推文 / 直播逐字稿 / 视频文案，统一进这张表
CREATE TABLE IF NOT EXISTS posts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  platform    TEXT,                -- douyin / xhs / book / tweet / live ...
  author      TEXT,
  title       TEXT,
  content     TEXT,
  url         TEXT UNIQUE,
  word_count  INTEGER DEFAULT 0,
  topic       TEXT,                -- 归类，可空
  created_at  INTEGER,
  fetched_at  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);
CREATE INDEX IF NOT EXISTS idx_posts_topic    ON posts(topic);

-- 观点：从素材里抽出来的一句话洞察
CREATE TABLE IF NOT EXISTS insights (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id     INTEGER,
  text        TEXT NOT NULL,
  kind        TEXT,                -- 反直觉 / 方法论 / 数据 / 金句 ...
  score       REAL DEFAULT 0,
  created_at  INTEGER,
  FOREIGN KEY (post_id) REFERENCES posts(id)
);
CREATE INDEX IF NOT EXISTS idx_insights_post ON insights(post_id);

-- 选题：从观点组合出来的题目
CREATE TABLE IF NOT EXISTS topics (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT NOT NULL,
  angle       TEXT,
  source_ids  TEXT,                -- 来源观点 id，逗号分隔
  status      TEXT DEFAULT 'idea', -- idea / writing / done / dropped
  created_at  INTEGER
);

-- 成稿
CREATE TABLE IF NOT EXISTS drafts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id    INTEGER,
  title       TEXT,
  body        TEXT,
  platform    TEXT,
  status      TEXT DEFAULT 'draft',
  created_at  INTEGER,
  updated_at  INTEGER,
  FOREIGN KEY (topic_id) REFERENCES topics(id)
);

-- 钩子（开头第一句，用来测试吸引力）
CREATE TABLE IF NOT EXISTS hooks (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id    INTEGER,
  text        TEXT NOT NULL,
  style       TEXT,                -- 悬念 / 数字 / 反常识 / 提问 ...
  created_at  INTEGER,
  FOREIGN KEY (draft_id) REFERENCES drafts(id)
);

-- 书库（PDF/EPUB 解析后的块，供 books_query.py 查）
CREATE TABLE IF NOT EXISTS book_chunks (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  book_title  TEXT,
  author      TEXT,
  chapter     TEXT,
  chunk_no    INTEGER,
  content     TEXT,
  created_at  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_chunks_book ON book_chunks(book_title);

-- 采集流水（哪条链接抓过、成没成）
CREATE TABLE IF NOT EXISTS capture_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  url         TEXT,
  status      TEXT,                -- ok / fail
  reason      TEXT,
  created_at  INTEGER
);
"""


def main():
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    else:
        root = Path(os.environ.get('DSH_MEDIA_DATA') or (Path.home() / 'dsh-media-data'))

    db_path = root / 'media' / 'workbench.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    conn.commit()

    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()]
    conn.close()

    print(f'数据库: {db_path}')
    print(f'已建表: {", ".join(tables)}')
    print('空库，可以开始采集了。')


if __name__ == '__main__':
    main()
