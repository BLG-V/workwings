import type { ChatFileMeta } from '@/lib/chat-file'

const IMAGE_MAX_EDGE = 1280
const IMAGE_QUALITY = 0.82

function readAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('读取文件失败'))
    reader.readAsDataURL(file)
  })
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('图片解码失败'))
    img.src = src
  })
}

/** 压缩图片为 data URL，便于对话展示与本地存储 */
export async function createImagePreview(file: File): Promise<string> {
  const raw = await readAsDataURL(file)
  const img = await loadImage(raw)
  const scale = Math.min(1, IMAGE_MAX_EDGE / Math.max(img.width, img.height))
  const w = Math.max(1, Math.round(img.width * scale))
  const h = Math.max(1, Math.round(img.height * scale))
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) return raw
  ctx.drawImage(img, 0, 0, w, h)
  return canvas.toDataURL('image/jpeg', IMAGE_QUALITY)
}

export async function readTextFile(file: File, maxChars = 12000): Promise<string> {
  const text = await file.text()
  if (text.length <= maxChars) return text
  return `${text.slice(0, maxChars)}\n\n…（已截断，原文共 ${text.length} 字）`
}

export function isImageFile(file: File) {
  return file.type.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(file.name)
}

export function isTextFile(file: File) {
  if (file.type.startsWith('text/')) return true
  return /\.(txt|md|json|csv|ts|tsx|js|jsx|py|java|go|rs|css|html|xml|yml|yaml|log)$/i.test(
    file.name,
  )
}

export async function buildFileMeta(file: File): Promise<ChatFileMeta> {
  if (isImageFile(file)) {
    const previewUrl = await createImagePreview(file)
    return {
      name: file.name,
      size: file.size,
      type: file.type || 'image/*',
      kind: 'image',
      previewUrl,
    }
  }
  return {
    name: file.name,
    size: file.size,
    type: file.type || 'application/octet-stream',
    kind: isTextFile(file) ? 'text' : 'file',
  }
}

/** 把附件整理成发给模型的文本说明（官方 DeepSeek 暂不支持识图） */
export async function buildAttachmentPrompt(
  files: File[],
  metas: ChatFileMeta[],
): Promise<string> {
  if (!files.length) return ''

  const parts: string[] = [
    `【附件】用户本次上传了 ${files.length} 个文件：`,
  ]

  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    const meta = metas[i]
    if (meta.kind === 'image') {
      parts.push(
        `- 图片「${meta.name}」（约 ${Math.round(meta.size / 1024)}KB）。界面已展示缩略图；当前 DeepSeek 官方接口无法直接识图，请结合用户文字说明协助，不要声称「未检测到上传」。`,
      )
    } else if (meta.kind === 'text') {
      const content = await readTextFile(file)
      parts.push(`- 文本文件「${meta.name}」内容如下：\n\`\`\`\n${content}\n\`\`\``)
    } else {
      parts.push(
        `- 文件「${meta.name}」（${meta.type || '未知类型'}，约 ${Math.round(meta.size / 1024)}KB）。暂无法解析二进制内容，请请用户补充说明。`,
      )
    }
  }

  return parts.join('\n')
}
