export type DeepSeekModelId = 'deepseek-v4-flash' | 'deepseek-v4-pro'

export interface ChatTurn {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface DeepSeekResult {
  content: string
  reasoning?: string
  model: string
}

export interface StreamChatHandlers {
  onReasoningDelta?: (delta: string, full: string) => void
  onContentDelta?: (delta: string, full: string) => void
}

const SYSTEM_PROMPT = `你是「智流 MAWP」多 Agent 研发助手，帮助用户推进：需求分析 → 架构设计 → 代码编写 → 测试验证 → 部署上线。

回答必须使用简体中文，并采用「豆包式」排版（Markdown），让信息一眼可扫：

【结构】
1. 第一行用一句短标题（可用 # 或加粗），直接点题，不要寒暄堆砌
2. 紧跟 1～3 句总述：现状判断 + 核心建议；关键词用 **加粗**
3. 用 ## / ### 分小节；每节只讲一件事
4. 可执行项用有序列表；举例用无序列表；括号里补「用量/时机/注意」等短说明
5. 推荐做法前可加 ✅；需要避雷的单独成段，用 ❌ 开头，并放在引用块里，例如：
   > ❌ 少做：……（说明原因）
6. 需要用户补充信息时，文末用简短「还需要你补充：」列表，不要反问连环弹

【语气与密度】
- 像靠谱顾问当面说清，少空话、少客套、少重复
- 优先给可直接照做的方案，再解释为什么
- 不确定就明确说不确定，不要编造

【附件】
当消息含【附件】时，表示用户已上传文件；图片在前端已展示，你看不到像素，请结合文字与附件说明协助，不要说「未检测到上传」。`

function splitReasoning(reasoning: string): string[] {
  const lines = reasoning
    .split(/\n+/)
    .map((l) => l.replace(/^[\s\-*\d.、]+/, '').trim())
    .filter(Boolean)
  if (lines.length <= 1) {
    const chunks = reasoning
      .split(/[。；;\n]+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 4)
    return chunks.length ? chunks.slice(0, 12) : [reasoning.trim()].filter(Boolean)
  }
  return lines.slice(0, 16)
}

export function reasoningToSteps(reasoning?: string): string[] {
  if (!reasoning?.trim()) return []
  return splitReasoning(reasoning.trim())
}

function buildRequestBody(options: {
  model: DeepSeekModelId
  messages: ChatTurn[]
  deepThink?: boolean
  systemPrompt?: string
  stream: boolean
}) {
  const { model, messages, deepThink, systemPrompt, stream } = options
  const body: Record<string, unknown> = {
    model,
    messages: [
      { role: 'system', content: systemPrompt?.trim() || SYSTEM_PROMPT },
      ...messages.filter((m) => m.role !== 'system'),
    ],
    stream,
    thinking: { type: deepThink ? 'enabled' : 'disabled' },
  }
  if (deepThink) {
    body.reasoning_effort = 'high'
  }
  return body
}

async function parseErrorResponse(res: Response): Promise<never> {
  const raw = await res.text()
  let message = `DeepSeek 请求失败（HTTP ${res.status}）`
  try {
    const data = JSON.parse(raw) as { error?: { message?: string } }
    if (data.error?.message) message = data.error.message
  } catch {
    if (raw.trim()) message = raw.slice(0, 200)
  }
  throw new Error(message)
}

/** 流式对话：边收边回调 reasoning / content */
export async function streamChatWithDeepSeek(options: {
  model: DeepSeekModelId
  messages: ChatTurn[]
  deepThink?: boolean
  signal?: AbortSignal
  systemPrompt?: string
  onReasoningDelta?: (delta: string, full: string) => void
  onContentDelta?: (delta: string, full: string) => void
}): Promise<DeepSeekResult> {
  const { model, messages, deepThink, signal, systemPrompt, onReasoningDelta, onContentDelta } =
    options

  const res = await fetch('/api/deepseek/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(
      buildRequestBody({
        model,
        messages,
        deepThink,
        systemPrompt,
        stream: true,
      }),
    ),
    signal,
  })

  if (!res.ok) {
    await parseErrorResponse(res)
  }

  if (!res.body) {
    throw new Error('DeepSeek 未返回流式响应体')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let content = ''
  let reasoning = ''
  let resolvedModel = model

  const consumeData = (data: string) => {
    if (!data || data === '[DONE]') return
    let json: {
      model?: string
      error?: { message?: string }
      choices?: Array<{
        delta?: {
          content?: string | null
          reasoning_content?: string | null
        }
        message?: {
          content?: string | null
          reasoning_content?: string | null
        }
      }>
    }
    try {
      json = JSON.parse(data)
    } catch {
      return
    }
    if (json.error?.message) {
      throw new Error(json.error.message)
    }
    if (json.model) resolvedModel = json.model

    const delta = json.choices?.[0]?.delta
    const message = json.choices?.[0]?.message
    const reasoningPiece =
      delta?.reasoning_content ?? message?.reasoning_content ?? ''
    const contentPiece = delta?.content ?? message?.content ?? ''

    if (reasoningPiece) {
      reasoning += reasoningPiece
      onReasoningDelta?.(reasoningPiece, reasoning)
    }
    if (contentPiece) {
      content += contentPiece
      onContentDelta?.(contentPiece, content)
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\r?\n/)
    buffer = parts.pop() ?? ''
    for (const line of parts) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith(':')) continue
      if (trimmed.startsWith('data:')) {
        consumeData(trimmed.slice(5).trim())
      }
    }
  }

  if (buffer.trim()) {
    const trimmed = buffer.trim()
    if (trimmed.startsWith('data:')) {
      consumeData(trimmed.slice(5).trim())
    }
  }

  if (!content.trim() && !reasoning.trim()) {
    throw new Error('模型未返回有效内容')
  }

  return {
    content: content.trim() || '（模型仅返回了思考过程，未给出最终正文）',
    reasoning: reasoning.trim() || undefined,
    model: resolvedModel || model,
  }
}

/** 非流式（Studio 等场景）；内部仍走同一请求体结构 */
export async function chatWithDeepSeek(options: {
  model: DeepSeekModelId
  messages: ChatTurn[]
  deepThink?: boolean
  signal?: AbortSignal
  systemPrompt?: string
}): Promise<DeepSeekResult> {
  const { model, messages, deepThink, signal, systemPrompt } = options

  const res = await fetch('/api/deepseek/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(
      buildRequestBody({
        model,
        messages,
        deepThink,
        systemPrompt,
        stream: false,
      }),
    ),
    signal,
  })

  if (!res.ok) {
    await parseErrorResponse(res)
  }

  const raw = await res.text()
  let data: {
    error?: { message?: string }
    model?: string
    choices?: Array<{
      message?: {
        content?: string | null
        reasoning_content?: string | null
      }
    }>
  }

  try {
    data = JSON.parse(raw)
  } catch {
    throw new Error('DeepSeek 返回了无法解析的内容')
  }

  if (data.error?.message) {
    throw new Error(data.error.message)
  }

  const message = data.choices?.[0]?.message
  const content = (message?.content || '').trim()
  const reasoning = (message?.reasoning_content || '').trim() || undefined

  if (!content && !reasoning) {
    throw new Error('模型未返回有效内容')
  }

  return {
    content: content || '（模型仅返回了思考过程，未给出最终正文）',
    reasoning,
    model: data.model || model,
  }
}

export const DEEPSEEK_MODELS: Array<{
  id: DeepSeekModelId
  label: string
  desc: string
}> = [
  {
    id: 'deepseek-v4-flash',
    label: 'DeepSeek V4 Flash',
    desc: '更快更省，日常对话',
  },
  {
    id: 'deepseek-v4-pro',
    label: 'DeepSeek V4 Pro',
    desc: '更强推理，复杂任务',
  },
]
