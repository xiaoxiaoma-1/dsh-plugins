import os, shutil, sqlite3, tempfile, glob, sys

cands = []
roots = [
    os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Edge\User Data'),
    os.path.expandvars(r'%LOCALAPPDATA%\360Chrome\Chrome\User Data'),
    os.path.expandvars(r'%LOCALAPPDATA%\115Chrome\User Data'),
    os.path.expandvars(r'%LOCALAPPDATA%\ChromeCore\User Data'),
    os.path.expandvars(r'%APPDATA%\360se6\User Data'),
    os.path.expandvars(r'%APPDATA%\SogouExplorer\User Data'),
    os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data'),
]
for r in roots:
    if not os.path.isdir(r):
        continue
    for prof in os.listdir(r):
        for sub in [os.path.join(r, prof, 'Network', 'Cookies'), os.path.join(r, prof, 'Cookies')]:
            if os.path.isfile(sub):
                cands.append(sub)
    # 根目录下的 Cookies
    for sub in [os.path.join(r, 'Network', 'Cookies'), os.path.join(r, 'Cookies')]:
        if os.path.isfile(sub):
            cands.append(sub)

print('found cookie files:', len(cands))
tmpd = tempfile.mkdtemp()
for i, f in enumerate(cands):
    t = os.path.join(tmpd, f'c{i}.db')
    try:
        shutil.copy2(f, t)
    except Exception as e:
        print('copy fail', f, e); continue
    try:
        con = sqlite3.connect(t)
        rows = con.execute("select host_key, name, length(encrypted_value) from cookies where host_key like '%xiaoeknow%' or host_key like '%xetlk%'").fetchall()
        con.close()
        print(f'--- {f}  hits={len(rows)}')
        for h, n, l in rows[:20]:
            print('   ', h, n, l)
    except Exception as e:
        print('sqlite fail', f, e)
