import JSZip from 'jszip'
import { chatWithDeepSeek } from '@/lib/deepseek'
import {
  buildFlowchartUserPrompt,
  FLOWCHART_SYSTEM_PROMPT,
  parseFlowchartFromModel,
  type FlowchartPayload,
} from '@/lib/flowchart'
import { isTextFile, readTextFile } from '@/lib/file-utils'

async function readDocxText(file: File, maxChars = 18000): Promise<string> {
  const buf = await file.arrayBuffer()
  const zip = await JSZip.loadAsync(buf)
  const xml = await zip.file('word/document.xml')?.async('string')
  if (!xml) throw new Error(`无法解析 Word：${file.name}`)
  const text = xml
    .replace(/<w:tab[^/]*\/>/g, '\t')
    .replace(/<w:br[^/]*\/>/g, '\n')
    .replace(/<\/w:p>/g, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
  if (!text) throw new Error(`Word 无文本内容：${file.name}`)
  if (text.length <= maxChars) return text
  return `${text.slice(0, maxChars)}\n\n…（已截断，原文约 ${text.length} 字）`
}

/** 从上传文件抽取可供构图的文本 */
export async function extractTextsForFlowchart(
  files: File[],
): Promise<{ text: string; notes: string[] }> {
  if (!files.length) return { text: '', notes: [] }
  const chunks: string[] = []
  const notes: string[] = []

  for (const file of files) {
    const name = file.name
    try {
      if (isTextFile(file) || /\.(txt|md|markdown|csv|json|log)$/i.test(name)) {
        const t = await readTextFile(file, 18000)
        chunks.push(`### 文件：${name}\n${t}`)
        notes.push(`已读取文本：${name}`)
      } else if (/\.docx$/i.test(name)) {
        const t = await readDocxText(file)
        chunks.push(`### 文件：${name}\n${t}`)
        notes.push(`已解析 Word：${name}`)
      } else if (/\.pdf$/i.test(name)) {
        notes.push(`暂不支持直接解析 PDF「${name}」，请转 Word/文本或粘贴关键段落`)
      } else if (file.type.startsWith('image/')) {
        notes.push(`图片「${name}」无法识图构图，请补充文字说明或上传文档`)
      } else {
        notes.push(`跳过不支持的文件类型：${name}`)
      }
    } catch (err) {
      notes.push(
        `读取「${name}」失败：${err instanceof Error ? err.message : '未知错误'}`,
      )
    }
  }

  return { text: chunks.join('\n\n'), notes }
}

export async function generateFlowchart(opts: {
  topic: string
  files?: File[]
  signal?: AbortSignal
}): Promise<FlowchartPayload> {
  const { text: fileText, notes } = await extractTextsForFlowchart(
    opts.files || [],
  )
  const topic = opts.topic.trim()

  if (!topic && !fileText.trim()) {
    throw new Error('请描述流程，或上传 txt/md/docx 文档后再生成')
  }

  const result = await chatWithDeepSeek({
    model: 'deepseek-v4-flash',
    deepThink: false,
    systemPrompt: FLOWCHART_SYSTEM_PROMPT,
    messages: [
      {
        role: 'user',
        content: buildFlowchartUserPrompt({ topic: topic || '根据附件生成流程图', fileText }),
      },
    ],
    signal: opts.signal,
  })

  const parsed = parseFlowchartFromModel(
    result.content,
    topic.slice(0, 24) || '流程图',
  )

  return {
    ...parsed,
    createdAt: new Date().toISOString(),
    sourceHint: notes.length ? notes.join('；') : undefined,
  }
}
