/** 博查 Bocha Web Search（经 Vite 代理，密钥不进前端包） */

export interface WebSearchHit {
  title: string
  url: string
  snippet: string
  siteName?: string
}

export interface WebSearchResult {
  query: string
  hits: WebSearchHit[]
  /** 注入给模型的上下文 */
  contextText: string
}

function detectFreshness(query: string): string {
  if (/今天|今日|现在|实时|刚才|最新|气温|天气|气温|多少度/.test(query)) {
    return 'oneDay'
  }
  if (/本周|这周|近几天|近日/.test(query)) return 'oneWeek'
  if (/本月|这个月/.test(query)) return 'oneMonth'
  return 'noLimit'
}

function formatHits(hits: WebSearchHit[]): string {
  if (!hits.length) return '（未检索到有效网页结果）'
  return hits
    .map((h, i) => {
      const site = h.siteName ? `｜${h.siteName}` : ''
      return `[${i + 1}] ${h.title}${site}\n链接：${h.url}\n摘要：${h.snippet}`
    })
    .join('\n\n')
}

export async function searchWeb(
  query: string,
  opts?: { count?: number; signal?: AbortSignal },
): Promise<WebSearchResult> {
  const q = query.trim()
  if (!q) {
    throw new Error('搜索词为空')
  }

  const res = await fetch('/api/bocha/v1/web-search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: q,
      freshness: detectFreshness(q),
      summary: true,
      count: opts?.count ?? 8,
    }),
    signal: opts?.signal,
  })

  const raw = await res.text()
  let data: {
    code?: number
    msg?: string
    message?: string
    data?: {
      webPages?: {
        value?: Array<{
          name?: string
          url?: string
          summary?: string
          snippet?: string
          siteName?: string
        }>
      }
    }
  }

  try {
    data = JSON.parse(raw)
  } catch {
    throw new Error(
      res.ok ? '联网搜索返回无法解析' : `联网搜索失败（HTTP ${res.status}）`,
    )
  }

  if (!res.ok || (data.code != null && data.code !== 200)) {
    throw new Error(
      data.msg || data.message || `联网搜索失败（HTTP ${res.status}）`,
    )
  }

  const pages = data.data?.webPages?.value ?? []
  const hits: WebSearchHit[] = pages
    .map((p) => ({
      title: (p.name || '').trim() || '无标题',
      url: (p.url || '').trim(),
      snippet: (p.summary || p.snippet || '').trim() || '无摘要',
      siteName: p.siteName?.trim(),
    }))
    .filter((h) => h.url)

  const contextText = [
    `检索词：${q}`,
    `时间偏好：${detectFreshness(q)}`,
    '',
    formatHits(hits),
  ].join('\n')

  return { query: q, hits, contextText }
}
