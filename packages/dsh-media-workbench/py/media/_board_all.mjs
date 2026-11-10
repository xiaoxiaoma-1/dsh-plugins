// 8 个板块并发 3 路跑 _board_test.mjs（共用同一份 prompt，避免两处漂移）
import { spawn } from 'node:child_process'

const BOARDS = ['商业与变现', '内容创作', 'AI 与工具', '心理与人性', '语言与思维', '国学与哲学', '身心与生活', '权谋与政治']
const CONC = 3

function one(board) {
  return new Promise((res) => {
    const c = spawn(process.execPath, ['E:\\desktop\\media\\_board_test.mjs', board, '10'], {
      cwd: 'E:\\desktop\\media', windowsHide: true,
    })
    let out = ''
    c.stdout.setEncoding('utf8')
    c.stdout.on('data', (d) => { out += d })
    c.stderr.setEncoding('utf8')
    c.stderr.on('data', (d) => { out += d })
    c.on('close', (code) => {
      const keep = out.split('\n').filter((l) => /^\[|模型给了|落库|失败/.test(l))
      console.log(`=== ${board} (exit ${code}) ===\n` + keep.join('\n') + '\n')
      res({ board, code, out })
    })
  })
}

let idx = 0
await Promise.all(Array.from({ length: CONC }, async () => {
  while (idx < BOARDS.length) {
    const b = BOARDS[idx++]
    await one(b)
  }
}))
console.log('全部板块跑完')
