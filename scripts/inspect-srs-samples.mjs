import fs from 'node:fs'
import path from 'node:path'

const xml = fs.readFileSync(
  path.join(process.env.TEMP, 'srs-outline', 'document.xml'),
  'utf8',
)

// first heading1 paragraph full XML sample
const h1 = xml.match(/<w:p[^>]*>[\s\S]*?w:pStyle\s+w:val="Heading1"[\s\S]*?<\/w:p>/)
const h2 = xml.match(/<w:p[^>]*>[\s\S]*?w:pStyle\s+w:val="Heading2"[\s\S]*?<\/w:p>/)
const bullet = xml.match(/<w:p[^>]*>[\s\S]*?w:pStyle\s+w:val="ListBullet"[\s\S]*?<\/w:p>/)
const tbl = xml.match(/<w:tbl>[\s\S]*?<\/w:tbl>/)
const cover = [...xml.matchAll(/<w:p[\s\S]*?<\/w:p>/g)].slice(0, 7)

const out = path.join(process.env.TEMP, 'srs-outline', 'samples.xml')
fs.writeFileSync(
  out,
  [
    '=== COVER0 ===',
    cover[0][0],
    '=== H1 ===',
    h1?.[0] || '',
    '=== H2 ===',
    h2?.[0] || '',
    '=== BULLET ===',
    bullet?.[0] || '',
    '=== TABLE (first 2500) ===',
    (tbl?.[0] || '').slice(0, 2500),
  ].join('\n\n'),
)
console.log('wrote', out)
console.log('tables', (xml.match(/<w:tbl>/g) || []).length)
console.log('sectPr', (xml.match(/<w:sectPr[\s\S]*?<\/w:sectPr>/g) || [])[0]?.slice(0, 500))
