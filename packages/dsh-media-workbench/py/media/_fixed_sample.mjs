// 修正版：同一段台词，但「不再逐句拨音调」——整轮一次合成、音色参数固定、停顿固定 0.25s
import { spawn } from 'node:child_process'
import fs from 'node:fs'

const PY = 'E:\\tools\\asr\\.venv\\Scripts\\python.exe'
const FF = 'C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe'
const DIR = 'E:\\desktop\\media\\_fx'
fs.mkdirSync(DIR, { recursive: true })

const A = 'zh-CN-XiaoxiaoNeural'
const B = 'zh-CN-YunxiNeural'

// 每一轮是「一个人连着说完的一段话」，一次合成，不再拆碎
const TURNS = [
  [A, '诶，等一下，你这说法我有点没听懂啊。'],
  [B, '就是，粉丝越多，其实越难赚。一开始我也不信，真的，我当时还跟人吵过。'],
  [A, '不是，你、你这个逻辑反了吧？你到底想说啥。'],
  [B, '小红书把账号放在不同的池子里。一万粉一个池子，十万粉又是另一个。你在小池子里能乱杀，进了大池子，就是被人乱杀。'],
  [A, '那我懂了，池子越大，对手越狠。啧，那这么讲，涨粉还成负担了。'],
  [B, '不是负担，是换赛道。你原来那套打法，在新池子里，它不认了。先想清楚一件事：你要的是钱，还是那个数字。'],
]

function run(cmd, args) {
  return new Promise((res, rej) => {
    const c = spawn(cmd, args, { windowsHide: true })
    let e = ''
    c.stderr.on('data', (d) => { e += d })
    c.on('close', (code) => (code === 0 ? res() : rej(new Error(e.slice(-200)))))
  })
}

const order = []
await run(FF, ['-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '0.25', `${DIR}\\gap.mp3`])
for (let i = 0; i < TURNS.length; i++) {
  const [voice, text] = TURNS[i]
  const f = `${DIR}\\t${i}.mp3`
  await run(PY, ['-m', 'edge_tts', '--voice', voice, '--text', text, '--write-media', f])
  order.push(f)
  order.push(`${DIR}\\gap.mp3`)
}
fs.writeFileSync(`${DIR}\\list.txt`, order.map((f) => `file '${f.replace(/\\/g, '/')}'`).join('\n'), 'utf8')
await run(FF, ['-y', '-f', 'concat', '-safe', '0', '-i', `${DIR}\\list.txt`, '-c:a', 'libmp3lame', '-b:a', '128k',
  'E:\\desktop\\播客样音_整轮合成版.mp3'])
console.log('done', Math.round(fs.statSync('E:\\desktop\\播客样音_整轮合成版.mp3').size / 1024) + ' KB')
