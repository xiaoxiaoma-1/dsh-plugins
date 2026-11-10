// 情感样音：同一段对话，用 rate/pitch 做语气差别（疑惑、笑、放缓、打断、感叹）
import { spawn } from 'node:child_process'
import fs from 'node:fs'

const PY = 'E:\\tools\\asr\\.venv\\Scripts\\python.exe'
const FF = 'C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe'
const DIR = 'E:\\desktop\\media\\_emo'
fs.mkdirSync(DIR, { recursive: true })

const A = 'zh-CN-XiaoxiaoNeural'
const B = 'zh-CN-YunxiNeural'

// [voice, text, rate, pitch]
const LINES = [
  [A, '诶？你是说，粉丝越多，反而越难赚钱？', '+8%', '+15Hz'],
  [B, '哈哈，对。我第一次听也觉得扯。', '+5%', '+5Hz'],
  [A, '那你给我说说，这到底是怎么个逻辑？', '+0%', '+8Hz'],
  [B, '嗯……这么讲吧。小红书把账号放在不同的池子里。一万粉，一个池子。十万粉，另一个池子。', '-8%', '-5Hz'],
  [A, '等等，所以池子越大，对手越强？', '+10%', '+12Hz'],
  [B, '对，就是这个意思。你在小池子里能乱杀，进了大池子，就是被人乱杀。', '-3%', '-2Hz'],
  [A, '啧，那涨粉还成负资产了。', '+6%', '+10Hz'],
  [B, '不是负资产，是换赛道。你原来的打法，在新池子里不认了。', '-5%', '-3Hz'],
]

function run(cmd, args) {
  return new Promise((res, rej) => {
    const c = spawn(cmd, args, { windowsHide: true })
    let err = ''
    c.stderr.on('data', (d) => { err += d })
    c.on('close', (code) => (code === 0 ? res() : rej(new Error(err.slice(-300)))))
  })
}

const files = []
for (let i = 0; i < LINES.length; i++) {
  const [voice, text, rate, pitch] = LINES[i]
  const f = `${DIR}\\s${i}.mp3`
  await run(PY, ['-m', 'edge_tts', '--voice', voice, '--rate=' + rate, '--pitch=' + pitch,
    '--text', text, '--write-media', f])
  files.push(f)
}
// 句间 220ms 静音
await run(FF, ['-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '0.22', `${DIR}\\gap.mp3`])
const order = []
for (let i = 0; i < files.length; i++) { order.push(files[i]); order.push(`${DIR}\\gap.mp3`) }
fs.writeFileSync(`${DIR}\\list.txt`, order.map((f) => `file '${f.replace(/\\/g, '/')}'`).join('\n'), 'utf8')
await run(FF, ['-y', '-f', 'concat', '-safe', '0', '-i', `${DIR}\\list.txt`,
  '-af', 'loudnorm', '-c:a', 'libmp3lame', '-b:a', '96k',
  'E:\\desktop\\播客样音_情感版.mp3'])
const st = fs.statSync('E:\\desktop\\播客样音_情感版.mp3')
console.log('done', Math.round(st.size / 1024) + ' KB')
