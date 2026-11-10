import { spawn } from 'node:child_process'

const PY = 'E:\\tools\\asr\\.venv\\Scripts\\python.exe'
const DB = 'E:\\desktop\\media\\workbench.db'

// 与 index.js 里 TOPICS_PY 完全一致
const TOPICS_PY = [
  'import sqlite3, json, sys',
  'db, limit = sys.argv[1], int(sys.argv[2])',
  'c = sqlite3.connect(db)',
  'rows = c.execute("select id, day, title, angle, hook, score, level, board from pool_topics where (status is null or status not in (\'used\',\'archived\')) order by day desc, score desc limit ?", (limit,)).fetchall()',
  'out = [{"id": r[0], "day": r[1], "title": r[2], "angle": r[3], "hook": r[4], "score": r[5], "level": r[6], "board": r[7]} for r in rows]',
  'print(json.dumps({"topics": out}, ensure_ascii=False))',
].join('\n')

function runPyJson(code, args = []) {
  return new Promise((resolve, reject) => {
    const proc = spawn(PY, ['-X', 'utf8', '-c', code, ...args], { stdio: ['ignore', 'pipe', 'pipe'] })
    let out = '', err = ''
    proc.stdout.on('data', (d) => { out += d })
    proc.stderr.on('data', (d) => { err += d })
    proc.on('error', reject)
    proc.on('close', (code2) => {
      if (code2 !== 0) return reject(new Error((err || '').slice(-400) || `python exit ${code2}`))
      const lines = String(out).trim().split('\n').filter(Boolean)
      try {
        resolve(JSON.parse(lines[lines.length - 1] || '{}'))
      } catch (e) {
        reject(new Error('JSON 解析失败: ' + String(out).slice(0, 200)))
      }
    })
  })
}

try {
  const r = await runPyJson(TOPICS_PY, [DB, '3'])
  console.log('成功，取到', (r.topics || []).length, '条')
  for (const t of r.topics || []) console.log('  ', t.score, t.title)
} catch (e) {
  console.log('失败:', e.message)
}
