import fs from 'node:fs'
import JSZip from 'jszip'

const p = process.argv[2]
if (!p || !fs.existsSync(p)) {
  console.error('usage: node inspect-pptx.mjs <path>')
  process.exit(1)
}
console.log('file', p, fs.statSync(p).size)
const z = await JSZip.loadAsync(fs.readFileSync(p))
const slides = Object.keys(z.files)
  .filter((f) => /^ppt\/slides\/slide\d+\.xml$/.test(f))
  .sort((a, b) => +a.match(/slide(\d+)/)[1] - +b.match(/slide(\d+)/)[1])
console.log('slides', slides.length)
for (const f of slides) {
  const xml = await z.file(f).async('string')
  const texts = [...xml.matchAll(/<a:t[^>]*>([\s\S]*?)<\/a:t>/g)]
    .map((m) => m[1].replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').trim())
    .filter(Boolean)
  const uniq = []
  for (const t of texts) if (!uniq.includes(t)) uniq.push(t)
  console.log(f.match(/slide(\d+)/)[1] + ':', uniq.slice(0, 10).join(' | '))
}
