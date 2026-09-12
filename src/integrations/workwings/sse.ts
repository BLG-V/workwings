import { getWorkWingsHeaders, WORKWINGS_BASE } from './auth'
import type { WorkWingsStreamEvent, WorkWingsStreamHandlers } from './types'

export interface WorkWingsStreamOptions extends WorkWingsStreamHandlers {
  after?: number
  signal?: AbortSignal
}

interface SseFrame {
  id: string | null
  event: string
  data: string
}

function parseFrames(buffer: string): { frames: SseFrame[]; rest: string } {
  const frames: SseFrame[] = []
  let rest = buffer

  let splitAt = rest.search(/\r?\n\r?\n/)
  while (splitAt >= 0) {
    const raw = rest.slice(0, splitAt)
    const match = rest.slice(splitAt).match(/^\r?\n\r?\n/)
    rest = rest.slice(splitAt + (match?.[0].length || 2))
    splitAt = rest.search(/\r?\n\r?\n/)
    if (!raw.trim() || raw.trimStart().startsWith(':')) continue
    const lines = raw.split(/\r?\n/)
    let id: string | null = null
    let event = 'message'
    const data: string[] = []
    for (const line of lines) {
      if (!line || line.startsWith(':')) continue
      const colon = line.indexOf(':')
      const field = colon >= 0 ? line.slice(0, colon) : line
      const value = colon >= 0 ? line.slice(colon + 1).replace(/^ /, '') : ''
      if (field === 'id') id = value
      if (field === 'event') event = value || 'message'
      if (field === 'data') data.push(value)
    }
    if (data.length > 0) frames.push({ id, event, data: data.join('\n') })
  }
  return { frames, rest }
}

function parseEvent(frame: SseFrame): WorkWingsStreamEvent | null {
  if (frame.event !== 'workflow') return null
  try {
    return JSON.parse(frame.data) as WorkWingsStreamEvent
  } catch {
    return null
  }
}

export async function streamWorkflowRun(
  runId: string,
  options: WorkWingsStreamOptions = {},
): Promise<void> {
  const params = new URLSearchParams()
  if (options.after != null && options.after > 0) {
    params.set('after', String(options.after))
  }
  const suffix = params.toString() ? `?${params.toString()}` : ''
  const headers = getWorkWingsHeaders({ Accept: 'text/event-stream' })
  if (options.after != null && options.after > 0) {
    headers.set('Last-Event-ID', String(options.after))
  }
  const res = await fetch(
    `${WORKWINGS_BASE}/workflow-runs/${encodeURIComponent(runId)}/stream${suffix}`,
    { headers, signal: options.signal },
  )
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `stream failed ${res.status}`)
  }
  if (!res.body) throw new Error('stream body unavailable')

  const seen = new Set<string>()
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parsed = parseFrames(buffer)
      buffer = parsed.rest
      for (const frame of parsed.frames) {
        const event = parseEvent(frame)
        if (!event) continue
        const key = event.stream_event_id || String(event.sequence_no)
        if (seen.has(key)) continue
        seen.add(key)
        options.onEvent?.(event)
      }
    }
  } catch (error) {
    if (!options.signal?.aborted) {
      options.onError?.(error instanceof Error ? error : new Error('stream failed'))
    }
  } finally {
    reader.releaseLock()
    options.onClose?.()
  }
}
