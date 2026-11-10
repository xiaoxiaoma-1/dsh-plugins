# -*- coding: utf-8 -*-
"""ZipCrypto 密码找回：字典 + 数字穷举。

全部加密包都是 ZipCrypto（不是 AES），可以用「解密 12 字节本地头 + 校验 CRC 高字节」秒判。
找到的密码会记下来，供批量解压用。
"""
import itertools
import os
import string
import sys
import time
import zipfile

ROOT = r"E:\wengao"

COMMON = [
    "123456", "1234567", "12345678", "123456789", "1234567890", "888888", "88888888",
    "666666", "111111", "000000", "520520", "1314520", "1234", "12345", "0000",
    "admin", "admin123", "abc123", "abcd1234", "qwerty", "11111111", "222222",
    "999999", "147258", "1qaz2wsx", "asd123", "a123456", "qq123456", "woshishui",
    "baidu", "www", "dys", "xinyin", "fangsheng", "fangfeng", "douxiaoshuo",
]

SERIES = [
    "guiguzi", "guigu", "ggz", "guiguzi123", "guiguzi888", "guiguzi666",
    "diziwang", "diziwangxue", "diwangxue", "quanmou", "quanmou888",
    "qiangzhe", "qiangzhe888", "qiangzhe666", "shenggu", "shenggu888",
    "tianxiawumou", "zhifuxiaoren", "kaoqiaozhishu", "wumou",
    "maoxuan", "maozedong", "mq", "maoxuanjinghua",
    "guixue", "zhishang", "renxing", "tianshu", "renxingtianshu",
    "ziliaoku", "zy", "zy123456", "123", "abc", "a1b2c3",
]


def first_entry_head(zf):
    for i in zf.infolist():
        if i.is_dir() or not (i.flag_bits & 0x1):
            continue
        return i
    return None


def load_blob(path, info):
    """读本地文件头 12 字节 + 需要的校验字节。"""
    with open(path, "rb") as f:
        f.seek(info.header_offset)
        head = f.read(30)
        if head[:4] != b"PK\x03\x04":
            return None
        nlen = int.from_bytes(head[26:28], "little")
        xlen = int.from_bytes(head[28:30], "little")
        f.seek(info.header_offset + 30 + nlen + xlen)
        return f.read(12)


def make_check(info):
    # bit3=1 时有 data descriptor，此时用 time 的高字节；否则用 CRC 高字节
    if info.flag_bits & 0x8:
        return ((info.date_time[3] << 8) | info.date_time[4]) >> 8 & 0xFF, 11
    return (info.CRC >> 24) & 0xFF, 11


def crack_one(path, info, candidates, deadline):
    """先做 12 字节快速筛，命中后再用 zipfile 真解一次确认（避免 CRC 1/256 假阳性）。"""
    blob = load_blob(path, info)
    if not blob or len(blob) < 12:
        return None
    chk, idx = make_check(info)
    dec = zipfile._ZipDecrypter
    zf = zipfile.ZipFile(path)
    n = 0
    try:
        for pwd in candidates:
            if time.time() > deadline:
                return ("TIMEOUT", n)
            n += 1
            try:
                z = dec(pwd.encode("utf-8"))
                hit = z(blob)[idx] == chk
            except Exception:
                continue
            if not hit:
                continue
            # 真解一次确认真伪
            try:
                with zf.open(info, pwd=pwd.encode("utf-8")) as s:
                    if s.read(4):
                        return (pwd, n)
            except Exception:
                continue
    finally:
        zf.close()
    return (None, n)


def gen_candidates():
    for p in COMMON:
        yield p
    for p in SERIES:
        yield p
    # 系列名 + 数字
    for base in ("guiguzi", "quanyou", "diziwang", "qiangzhe", "xinyin", "tianxia"):
        for i in range(0, 100):
            yield "%s%02d" % (base, i)
        for i in range(2020, 2027):
            yield "%s%d" % (base, i)
    # 纯数字 1~6 位
    for n in range(1, 1000000):
        yield str(n)
    # 常见英文+数字
    for w in ("abc", "qq", "aa", "wx", "vip", "a", "ab"):
        for i in range(0, 10000):
            yield "%s%d" % (w, i)


def main():
    targets = []
    for dp, _, fs in os.walk(ROOT):
        for f in fs:
            if not f.lower().endswith(".zip"):
                continue
            p = os.path.join(dp, f)
            try:
                zf = zipfile.ZipFile(p)
            except Exception:
                continue
            e = first_entry_head(zf)
            zf.close()
            if e is not None:
                targets.append((p, e))
    print("加密包 %d 个" % len(targets))
    if not targets:
        return

    found = {}
    for p, info in sorted(targets, key=lambda x: -os.path.getsize(x[0])):
        if any(v[0] == info.CRC for v in found.values()):
            pass
        name = os.path.basename(p)
        deadline = time.time() + 90
        pwd, tried = crack_one(p, info, gen_candidates(), deadline)
        if pwd == "TIMEOUT":
            print("  超时（试了 %d 个）  %s" % (tried, name[:50]))
        elif pwd:
            print("  ✅ 密码 = %s（试了 %d 个）  %s" % (pwd, tried, name[:50]))
            found[p] = (pwd, tried)
        else:
            print("  未命中（试了 %d 个）  %s" % (tried, name[:50]))

    if found:
        out = os.path.join(r"E:\desktop\书库盘点", "zip密码.txt")
        with open(out, "w", encoding="utf-8") as f:
            for p, (pwd, _) in found.items():
                f.write("%s\t%s\n" % (pwd, p))
        print("\n密码已存：", out)
    else:
        print("\n没试出来。需要更长的字典或你从源里找。")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
