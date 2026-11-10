// 口语化文本 + 节奏层：口水词、自我打断、不规则停顿、抢话
import { spawn } from 'node:child_process'
import fs from 'node:fs'

const PY = 'E:\\tools\\asr\\.venv\\Scripts\\python.exe'
const FF = 'C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe'
const DIR = 'E:\\desktop\\media\\_rh'
fs.mkdirSync(DIR, { recursive: true })

const A = 'zh-CN-XiaoxiaoNeural'
const B = 'zh-CN-YunxiNeural'

// [voice, text, rate, pitch, gapAfter(ms)]
const LINES = [
  [A, '诶，等一下，你这说法我有点没听懂啊，', '+6%', '+12Hz', 260],
  [B, '就是，粉丝越多，其实越难赚。', '-2%', '-2Hz', 180],
  [A, '不是，你、你这个逻辑反了吧？', '+12%', '+16Hz', 220],
  [B, '一开始我也不信。真的，我当时还跟人吵过。', '-4%', '-4Hz', 420],
  [A, '所以到底为啥啊，你说慢点。', '+6%', '+8Hz', 200],
  [B, '小红书把账号，放在不同的池子里。一万粉，一个池子；十万粉，又是另一个。', '-8%', '-6Hz', 520],
  [A, '那我懂了，池子越大，对手越狠。', '+8%', '+10Hz', 180],
  [B, '对。你在小池子里，能乱杀；进了大池子，就是被人乱杀。', '-6%', '-5Hz', 380],
  [A, '啧，那这么讲，涨粉还成负担了。', '+4%', '+6Hz', 240],
  [B, '不是负担，是换赛道。你原来那套打法，在新池子里，它不认了。', '-5%', '-4Hz', 300],
  [A, '行，那你说说，普通人该咋选。', '+2%', '+4Hz', 200],
  [B, '先想清楚一件事：你要的是钱，还是那个数字。这俩东西，在小红书上是反着走的。', '-7%', '-6Hz', 260],
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
for (let i = 0; i < LINES.length; i++) {
  const [voice, text, rate, pitch, gap] = LINES[i]
  const f = `${DIR}\\s${i}.mp3`
  await run(PY, ['-m', 'edge_tts', '--voice', voice, '--rate=' + rate, '--pitch=' + pitch, '--text', text, '--write-media', f])
  order.push(f)
  const g = `${DIR}\\g${i}.mp3`
  await run(FF, ['-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', (gap / 1000).toFixed(2), g])
  order.push(g)
}
fs.writeFileSync(`${DIR}\\list.txt`, order.map((f) => `file '${f.replace(/\\/g, '/')}'`).join('\n'), 'utf8')
await run(FF, ['-y', '-f', 'concat', '-safe', '0', '-i', `${DIR}\\list.txt`, '-c:a', 'libmp3lame', '-b:a', '128k',
  'E:\\desktop\\播客样音_口语节奏版.mp3'])
console.log('done', Math.round(fs.statSync('E:\\desktop\\播客样音_口语节奏版.mp3').size / 1024) + ' KB')
