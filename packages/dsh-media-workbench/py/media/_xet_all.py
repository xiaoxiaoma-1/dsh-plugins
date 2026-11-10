# -*- coding: utf-8 -*-
"""全量抓取：17 节音频地址 -> 下载 mp3（跳过已存在且完整）"""
import json, os, sys, time, requests

BASE = 'https://appae4y5du51721.h5.xiaoeknow.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0'
OUT = r'E:\desktop\media\_xet_audio'
os.makedirs(OUT, exist_ok=True)

cookies = json.load(open(r'E:\desktop\media\_xet_cookies.json', encoding='utf-8'))
S = requests.Session()
S.headers.update({'user-agent': UA, 'origin': BASE,
                  'referer': f'{BASE}/p/course/ecourse/course_2t0jKVikbwJAqt46SimVSewKDqQ',
                  'accept': 'application/json, text/plain, */*', 'accept-language': 'zh-CN,zh;q=0.9'})
for c in cookies:
    S.cookies.set(c['name'], c['value'], domain='.xiaoeknow.com')


def detail(rid):
    r = S.post(f'{BASE}/xe.course.business_go.video.detail_info.get/2.0.0',
               data={'bizData[resource_id]': rid, 'bizData[product_id]': '', 'bizData[opr_sys]': 'Win32'}, timeout=30)
    j = r.json()
    return (j.get('data', {}).get('video_info') if j.get('code') == 0 else None), j


def safe(s, n=40):
    s = (s or '').replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_')
    s = s.replace('"', '').replace('<', '').replace('>', '').replace('|', '_')
    return s[:n]


cat = json.load(open(r'E:\desktop\media\_xet_catalog_raw.json', encoding='utf-8'))
nodes = sorted(cat['data']['list'], key=lambda x: x.get('sort_value', 0))
print('nodes', len(nodes), flush=True)

manifest = []
for i, n in enumerate(nodes, 1):
    rid = n['resource_id']
    title = (n.get('resource_title') or n.get('chapter_title') or rid).strip()
    vi, raw = detail(rid)
    if not vi:
        print('DETAIL_FAIL', i, rid, str(raw)[:150], flush=True)
        manifest.append({'idx': i, 'rid': rid, 'title': title, 'ok': False})
        continue
    url = vi.get('video_audio_url') or ''
    sec = vi.get('video_length') or n.get('video_length') or 0
    fn = '%02d_%s.mp3' % (i, safe(title))
    path = os.path.join(OUT, fn)
    rec = {'idx': i, 'rid': rid, 'title': title, 'sec': sec, 'audio_url': url, 'file': fn, 'ok': bool(url)}
    manifest.append(rec)
    print('%02d %s sec=%s audio=%s' % (i, title[:34], sec, 'Y' if url else 'N'), flush=True)

json.dump(manifest, open(r'E:\desktop\media\_xet_manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 下载
for rec in manifest:
    if not rec.get('ok'):
        continue
    path = os.path.join(OUT, rec['file'])
    if os.path.exists(path) and os.path.getsize(path) > 100000:
        print('SKIP', rec['file'], os.path.getsize(path), flush=True)
        continue
    t0 = time.time()
    try:
        r = S.get(rec['audio_url'], headers={'referer': BASE + '/'}, stream=True, timeout=120)
        if r.status_code != 200:
            print('DL_FAIL', rec['file'], r.status_code, flush=True)
            rec['ok'] = False
            continue
        tmp = path + '.part'
        n = 0
        with open(tmp, 'wb') as f:
            for chunk in r.iter_content(262144):
                f.write(chunk); n += len(chunk)
        os.replace(tmp, path)
        print('DL', rec['file'], n, 'bytes %.1fs' % (time.time() - t0), flush=True)
        rec['bytes'] = n
    except Exception as e:
        print('DL_ERR', rec['file'], type(e).__name__, e, flush=True)
        rec['ok'] = False

json.dump(manifest, open(r'E:\desktop\media\_xet_manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
ok = [m for m in manifest if m.get('ok')]
print('DONE ok=%d total=%d total_sec=%d' % (len(ok), len(manifest), sum(m.get('sec') or 0 for m in ok)), flush=True)
