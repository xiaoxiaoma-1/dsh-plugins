import fs from 'node:fs'
const p = 'E:\\tools\\soulx-podcast\\cli\\podcast.py'
let s = fs.readFileSync(p, 'utf8')
const before = 'with open(args.json_path, "r") as f:'
const after = 'with open(args.json_path, "r", encoding="utf-8") as f:'
if (s.includes('encoding="utf-8"')) {
  console.log('已打过补丁')
} else if (s.includes(before)) {
  s = s.replace(before, after)
  fs.writeFileSync(p, s, 'utf8')
  console.log('已补 encoding=utf-8')
} else {
  console.log('没找到目标行，需要手工看')
}
