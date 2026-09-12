import JSZip from 'jszip'

/** 把写作正文（可含简易 Markdown）导出为可被 Word 打开的 .docx */
export async function buildWritingDocxBlob(opts: {
  title: string
  content: string
}): Promise<Blob> {
  const title = (opts.title || '未命名文档').trim()
  const body = stripLeadingTitle(opts.content || '').trim() || opts.content.trim()
  const paragraphs = toDocParagraphs(title, body)
  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    ${paragraphs}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>`

  const zip = new JSZip()
  zip.file(
    '[Content_Types].xml',
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>`,
  )
  zip.folder('_rels')!.file(
    '.rels',
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`,
  )
  const word = zip.folder('word')!
  word.file('document.xml', documentXml)
  word.folder('_rels')!.file(
    'document.xml.rels',
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>`,
  )

  return zip.generateAsync({
    type: 'blob',
    mimeType:
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  })
}

export async function downloadWritingDocx(title: string, content: string) {
  const safe = (title || '文档').replace(/[\\/:*?"<>|]/g, '_').slice(0, 60)
  const blob = await buildWritingDocxBlob({ title: safe, content })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${safe}.docx`
  a.click()
  URL.revokeObjectURL(url)
}

function stripLeadingTitle(markdown: string) {
  return markdown.replace(/^#{1,2}\s+.+\n+/, '')
}

function escapeXml(s: string) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function plainLine(s: string) {
  return escapeXml(
    s
      .replace(/^#{1,6}\s+/, '')
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\*(.*?)\*/g, '$1')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/^\s*[-*+]\s+/, '')
      .trim(),
  )
}

function toDocParagraphs(title: string, body: string): string {
  const blocks: string[] = []
  blocks.push(wParagraph(escapeXml(title), { bold: true, size: 36, after: 240 }))

  const chunks = body.split(/\n{2,}/).map((c) => c.trim()).filter(Boolean)
  for (const chunk of chunks) {
    const lines = chunk.split(/\n/).map((l) => l.trim()).filter(Boolean)
    const isHeading = /^#{2,6}\s+/.test(chunk) || (lines.length === 1 && /^#{1,6}\s+/.test(lines[0] || ''))
    if (isHeading) {
      blocks.push(
        wParagraph(plainLine(lines[0] || chunk), {
          bold: true,
          size: 28,
          before: 200,
          after: 120,
        }),
      )
      continue
    }
    for (const line of lines) {
      blocks.push(wParagraph(plainLine(line), { size: 24, after: 160, line: 360 }))
    }
  }
  return blocks.join('\n')
}

function wParagraph(
  text: string,
  opts: { bold?: boolean; size?: number; before?: number; after?: number; line?: number },
) {
  const size = opts.size ?? 24
  const bold = opts.bold ? '<w:b/>' : ''
  const spacing = `<w:spacing w:before="${opts.before ?? 0}" w:after="${opts.after ?? 120}" w:line="${opts.line ?? 360}" w:lineRule="auto"/>`
  return `<w:p>
  <w:pPr>${spacing}<w:jc w:val="both"/></w:pPr>
  <w:r>
    <w:rPr>${bold}<w:sz w:val="${size}"/><w:szCs w:val="${size}"/><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/></w:rPr>
    <w:t xml:space="preserve">${text}</w:t>
  </w:r>
</w:p>`
}
