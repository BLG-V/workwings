/** 文生图：Vite 代理 / 浏览器直连优先转 dataUrl；后端代理作增强 */

export type ImageGenSize = { width: number; height: number; label: string }

export type ImageGenResult = {
  topic: string
  prompt: string
  url: string
  width: number
  height: number
  sizeLabel: string
  styleHint: string
  seed: number
  provider: string
}

const STYLE_MAP: Array<{ re: RegExp; en: string; label: string }> = [
  { re: /动漫|二次元|漫画/, en: 'anime style, vibrant colors', label: '动漫' },
  { re: /插画|扁平|扁平风/, en: 'illustration, clean vector-like shapes', label: '插画' },
  { re: /水彩/, en: 'watercolor painting', label: '水彩' },
  { re: /油画|油画风/, en: 'oil painting, rich brush strokes', label: '油画' },
  { re: /像素|像素风/, en: 'pixel art', label: '像素' },
  { re: /赛博|赛博朋克/, en: 'cyberpunk, neon lights', label: '赛博' },
  { re: /写实|照片|写真|摄影/, en: 'photorealistic, natural lighting', label: '写实' },
  { re: /3d|三维|渲染/, en: '3d render, octane style', label: '3D' },
  { re: /素描|线稿/, en: 'pencil sketch, line art', label: '素描' },
]

function detectSize(text: string): ImageGenSize {
  if (/竖图|竖屏|手机壁纸|9\s*[:：]\s*16|9\/16|竖版/.test(text)) {
    return { width: 768, height: 1344, label: '竖图 9:16' }
  }
  if (/横图|横屏|宽屏|桌面壁纸|16\s*[:：]\s*9|16\/9|横版/.test(text)) {
    return { width: 1344, height: 768, label: '横图 16:9' }
  }
  if (/头像|正方形|1\s*[:：]\s*1|方图/.test(text)) {
    return { width: 1024, height: 1024, label: '方形 1:1' }
  }
  return { width: 1024, height: 1024, label: '方形 1:1' }
}

function detectStyle(text: string): { en: string; label: string } {
  for (const item of STYLE_MAP) {
    if (item.re.test(text)) return { en: item.en, label: item.label }
  }
  return { en: 'high quality, detailed, cinematic lighting', label: '默认精致' }
}

export function sanitizeImageTopic(raw: string) {
  return (
    raw
      .replace(/^「图像生成」\s*/i, '')
      .replace(
        /^(请生成图片[，,:：]?|请画[一]?张[，,:：]?|帮我画[，,:：]?|生成图像[，,:：]?|图像生成[：:]?|画面主题[：:]?|画一张[，,:：]?|做一张图[，,:：]?)/i,
        '',
      )
      .replace(/^画面主题[：:]\s*/i, '')
      .trim() || '未命名画面'
  )
}

async function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('图片读取失败'))
    reader.readAsDataURL(blob)
  })
}

async function fetchImageAsDataUrl(
  url: string,
  signal?: AbortSignal,
): Promise<string> {
  const res = await fetch(url, { signal, cache: 'no-store' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const blob = await res.blob()
  if (blob.size < 1200) throw new Error('图片过小')
  const type = blob.type || ''
  if (type && !type.startsWith('image/') && !type.includes('octet-stream')) {
    throw new Error('未返回图片')
  }
  return blobToDataUrl(blob)
}

function buildFetchUrls(
  prompt: string,
  width: number,
  height: number,
  seed: number,
): Array<{ url: string; label: string }> {
  const path = encodeURIComponent(prompt)
  const list: Array<{ url: string; label: string }> = []

  // 开发态：Vite 代理到 gen.pollinations.ai（不依赖后端是否重启）
  if (import.meta.env.DEV) {
    list.push({
      url: `/api/pollinations/image/${path}?model=flux&width=${width}&height=${height}&nologo=true&seed=${seed}`,
      label: 'Vite 代理 Flux',
    })
    list.push({
      url: `/api/pollinations/image/${path}?width=${width}&height=${height}&nologo=true&seed=${seed}`,
      label: 'Vite 代理默认',
    })
  }

  list.push({
    url: `https://image.pollinations.ai/prompt/${path}?width=${width}&height=${height}&nologo=true&seed=${seed}`,
    label: 'Pollinations 旧端',
  })
  list.push({
    url: `https://gen.pollinations.ai/image/${path}?model=flux&width=${width}&height=${height}&nologo=true&seed=${seed}`,
    label: 'Pollinations 新端',
  })

  return list
}

async function generateViaBackend(
  prompt: string,
  width: number,
  height: number,
  seed: number,
  signal?: AbortSignal,
): Promise<{ dataUrl: string; provider: string }> {
  const res = await fetch(`/api/mawp/image/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, width, height, seed }),
    signal,
  })
  if (res.status === 404) {
    throw new Error('后端图像接口未就绪（请重启 backend :8787）')
  }
  const data = (await res.json().catch(() => ({}))) as {
    ok?: boolean
    dataUrl?: string
    provider?: string
    detail?: string
  }
  if (!res.ok || !data.dataUrl) {
    const detail =
      typeof data.detail === 'string'
        ? data.detail
        : `后端生图失败 ${res.status}`
    throw new Error(detail)
  }
  return {
    dataUrl: data.dataUrl,
    provider: data.provider || 'Pollinations',
  }
}

/** 生成一张图 */
export async function generateImageFromTopic(
  topicRaw: string,
  signal?: AbortSignal,
): Promise<ImageGenResult> {
  const topic = sanitizeImageTopic(topicRaw)
  const size = detectSize(topic)
  const style = detectStyle(topic)
  const seed = Math.floor(Math.random() * 1_000_000_000)
  const prompt = [topic, style.en].join(', ').slice(0, 420)

  const errors: string[] = []

  // 1) 先走 Vite/直连（不依赖旧后端进程）
  for (const item of buildFetchUrls(prompt, size.width, size.height, seed)) {
    try {
      const dataUrl = await fetchImageAsDataUrl(item.url, signal)
      return {
        topic,
        prompt,
        url: dataUrl,
        width: size.width,
        height: size.height,
        sizeLabel: size.label,
        styleHint: style.label,
        seed,
        provider: item.label,
      }
    } catch (err) {
      errors.push(
        `${item.label}: ${err instanceof Error ? err.message : String(err)}`,
      )
    }
  }

  // 2) 后端代理兜底
  try {
    const via = await generateViaBackend(
      prompt,
      size.width,
      size.height,
      seed,
      signal,
    )
    return {
      topic,
      prompt,
      url: via.dataUrl,
      width: size.width,
      height: size.height,
      sizeLabel: size.label,
      styleHint: style.label,
      seed,
      provider: `${via.provider}（服务端）`,
    }
  } catch (err) {
    errors.push(err instanceof Error ? err.message : String(err))
  }

  throw new Error(
    `图像生成失败。${errors.slice(0, 2).join('；') || '服务繁忙'}。可重启后端或检查网络。`,
  )
}
