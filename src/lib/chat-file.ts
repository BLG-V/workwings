export interface ChatFileMeta {
  name: string
  size: number
  type?: string
  /** 图片预览 data URL，用于对话中展示 */
  previewUrl?: string
  kind?: 'image' | 'text' | 'file'
}

export interface ChatMessageRecord {
  id: string
  role: 'user' | 'assistant'
  content: string
  model?: string
  files?: ChatFileMeta[]
  thinking?: string[]
  thinkingDone?: boolean
}
