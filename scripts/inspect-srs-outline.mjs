import fs from 'node:fs'
import path from 'node:path'
import JSZip from 'jszip'

const src =
  'd:/wx/xwechat_files/wxid_xfn1hprdke1922_887b/msg/file/2026-08/02-需求规格说明书-大纲.docx'
const outDir = path.join(process.env.TEMP, 'srs-outline')
fs.mkdirSync(outDir, { recursive: true })

const buf = fs.readFileSync(src)
const z = await JSZip.loadAsync(buf)
const xml = await z.file('word/document.xml').async('string')
const styles = await z.file('word/styles.xml').async('string')
const numbering = z.file('word/numbering.xml')
  ? await z.file('word/numbering.xml').async('string')
  : ''
fs.writeFileSync(path.join(outDir, 'document.xml'), xml)
fs.writeFileSync(path.join(outDir, 'styles.xml'), styles)
if (numbering) fs.writeFileSync(path.join(outDir, 'numbering.xml'), numbering)

const paras = [...xml.matchAll(/<w:p[\s\S]*?<\/w:p>/g)].map((m) => m[0])
const textOf = (p) =>
  [...p.matchAll(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g)]
    .map((x) => x[1])
    .join('')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
const styleOf = (p) => {
  const m = p.match(/w:pStyle\s+w:val="([^"]+)"/)
  return m ? m[1] : ''
}
const numId = (p) => {
  const m = p.match(/w:numId\s+w:val="([^"]+)"/)
  return m ? m[1] : ''
}
const ilvl = (p) => {
  const m = p.match(/w:ilvl\s+w:val="([^"]+)"/)
  return m ? m[1] : ''
}

const lines = []
let i = 0
for (const p of paras) {
  const t = textOf(p).trim()
  if (!t) continue
  i++
  lines.push(
    `${String(i).padStart(3)} style=${styleOf(p) || 'Normal'} num=${numId(p)}:${ilvl(p)} | ${t}`,
  )
}
fs.writeFileSync(path.join(outDir, 'outline.txt'), lines.join('\n'), 'utf8')
console.log('paras', lines.length)
console.log(lines.slice(0, 80).join('\n'))
console.log('--- sample heading styles from styles.xml ---')
const styleNames = [
  ...styles.matchAll(/w:styleId="([^"]+)"[\s\S]*?<w:name\s+w:val="([^"]+)"/g),
]
  .slice(0, 40)
  .map((m) => `${m[1]} = ${m[2]}`)
console.log(styleNames.join('\n'))
