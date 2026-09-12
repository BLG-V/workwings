/** 腾讯云实时 ASR 客户端（ScriptProcessor 连续 PCM + Analyser 仅测音量） */

export type AsrServerMessage =
  | { type: 'ready'; voice_id?: string; message?: string }
  | { type: 'partial'; text: string; slice_type?: number; index?: number }
  | { type: 'final'; text: string; slice_type?: number; index?: number }
  | { type: 'done' }
  | { type: 'error'; message: string; code?: number }

export type VoiceSessionHandlers = {
  onPartial?: (text: string) => void
  onFinalSegment?: (text: string) => void
  onLevel?: (level: number) => void
  onError?: (message: string) => void
  onReady?: () => void
  onDone?: () => void
}

const TARGET_RATE = 16000
const FRAME_BYTES = 6400 // 200ms @ 16k s16le

/** HTTP 公网访问时浏览器不提供麦克风；返回不可用原因，可用则 null */
export function getVoiceInputUnavailableReason(): string | null {
  if (typeof window === 'undefined') return '仅浏览器环境可用'
  const host = window.location.hostname
  const isLocal = host === 'localhost' || host === '127.0.0.1'
  if (!window.isSecureContext && !isLocal) {
    return '当前为 HTTP 访问，浏览器不允许使用麦克风。请使用 HTTPS 访问，或在本地 localhost 开发时使用语音。'
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return '当前浏览器不支持麦克风，请使用 Chrome / Edge 等现代浏览器。'
  }
  return null
}

function asrWsUrl(): string {
  if (import.meta.env.DEV) {
    return 'ws://127.0.0.1:8787/api/asr/realtime'
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api/mawp/asr/realtime`
}

function downsample(input: Float32Array, inRate: number, outRate: number): Float32Array {
  if (inRate === outRate) return input.slice()
  const ratio = inRate / outRate
  const outLen = Math.max(1, Math.floor(input.length / ratio))
  const out = new Float32Array(outLen)
  for (let i = 0; i < outLen; i += 1) {
    const idx = Math.min(input.length - 1, Math.floor(i * ratio))
    out[i] = input[idx] ?? 0
  }
  return out
}

function floatToS16le(float32: Float32Array, gain: number): Uint8Array {
  const out = new Uint8Array(float32.length * 2)
  const view = new DataView(out.buffer)
  for (let i = 0; i < float32.length; i += 1) {
    let s = (float32[i] ?? 0) * gain
    if (s > 1) s = 1
    if (s < -1) s = -1
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return out
}

export class TencentVoiceSession {
  private ws: WebSocket | null = null
  private stream: MediaStream | null = null
  private audioCtx: AudioContext | null = null
  private processor: ScriptProcessorNode | null = null
  private analyser: AnalyserNode | null = null
  private source: MediaStreamAudioSourceNode | null = null
  private zeroGain: GainNode | null = null
  private raf = 0
  private sendTimer: number | null = null
  private pcmChunks: Uint8Array[] = []
  private pcmBytes = 0
  private closed = false
  private wsReady = false
  private handlers: VoiceSessionHandlers
  private committed = ''
  private currentPartial = ''
  private bytesSent = 0
  private peakLevel = 0
  private agcGain = 3

  constructor(handlers: VoiceSessionHandlers = {}) {
    this.handlers = handlers
  }

  get transcript(): string {
    return `${this.committed}${this.currentPartial}`.trim()
  }

  get sentBytes(): number {
    return this.bytesSent
  }

  get peak(): number {
    return this.peakLevel
  }

  private enqueue(pcm: Uint8Array) {
    this.pcmChunks.push(pcm)
    this.pcmBytes += pcm.length
  }

  private takeBytes(n: number): Uint8Array | null {
    if (this.pcmBytes < n) return null
    const out = new Uint8Array(n)
    let offset = 0
    while (offset < n && this.pcmChunks.length) {
      const head = this.pcmChunks[0]!
      const need = n - offset
      if (head.length <= need) {
        out.set(head, offset)
        offset += head.length
        this.pcmChunks.shift()
      } else {
        out.set(head.subarray(0, need), offset)
        this.pcmChunks[0] = head.subarray(need)
        offset += need
      }
    }
    this.pcmBytes -= n
    return out
  }

  private flushFrames() {
    if (this.closed || !this.wsReady || this.ws?.readyState !== WebSocket.OPEN) return
    while (this.pcmBytes >= FRAME_BYTES) {
      const frame = this.takeBytes(FRAME_BYTES)
      if (!frame) break
      const packet = new Uint8Array(frame.length)
      packet.set(frame)
      try {
        this.ws.send(packet)
        this.bytesSent += packet.length
      } catch {
        break
      }
    }
  }

  private startMicGraph(ctx: AudioContext) {
    if (!this.stream) return
    const source = ctx.createMediaStreamSource(this.stream)
    this.source = source

    const analyser = ctx.createAnalyser()
    analyser.fftSize = 512
    analyser.smoothingTimeConstant = 0.2
    this.analyser = analyser

    // 连续非重叠缓冲（4096 @ 48k ≈ 85ms）
    const processor = ctx.createScriptProcessor(4096, 1, 1)
    this.processor = processor
    processor.onaudioprocess = (e) => {
      if (this.closed) return
      const input = e.inputBuffer.getChannelData(0)
      // 统计音量
      let sum = 0
      for (let i = 0; i < input.length; i += 1) {
        const v = input[i] ?? 0
        sum += v * v
      }
      const rms = Math.sqrt(sum / input.length)
      this.peakLevel = Math.max(this.peakLevel, rms)
      if (rms > 0.001 && rms < 0.06) {
        this.agcGain = Math.min(10, 0.4 / rms)
      } else if (rms >= 0.06) {
        this.agcGain = Math.max(1.5, this.agcGain * 0.92)
      }

      const copy = new Float32Array(input.length)
      copy.set(input)
      const down = downsample(copy, ctx.sampleRate, TARGET_RATE)
      this.enqueue(floatToS16le(down, this.agcGain))
    }

    const zero = ctx.createGain()
    zero.gain.value = 0
    this.zeroGain = zero

    // source → processor → zero → destination（保活）
    // source → analyser（音量 UI）
    source.connect(processor)
    source.connect(analyser)
    processor.connect(zero)
    zero.connect(ctx.destination)

    const levelBuf = new Uint8Array(analyser.fftSize)
    const tick = () => {
      if (this.closed || !this.analyser) return
      this.analyser.getByteTimeDomainData(levelBuf)
      let sum = 0
      for (let i = 0; i < levelBuf.length; i += 1) {
        const v = ((levelBuf[i] ?? 128) - 128) / 128
        sum += v * v
      }
      this.handlers.onLevel?.(Math.min(1, Math.sqrt(sum / levelBuf.length) * 5))
      this.raf = requestAnimationFrame(tick)
    }
    this.raf = requestAnimationFrame(tick)
  }

  async start(): Promise<void> {
    this.closed = false
    this.wsReady = false
    this.committed = ''
    this.currentPartial = ''
    this.pcmChunks = []
    this.pcmBytes = 0
    this.bytesSent = 0
    this.peakLevel = 0
    this.agcGain = 3

    const micBlock = getVoiceInputUnavailableReason()
    if (micBlock) {
      throw new Error(micBlock)
    }

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: true,
      },
      video: false,
    })

    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext
    const ctx = new AudioCtx()
    this.audioCtx = ctx
    if (ctx.state === 'suspended') await ctx.resume()

    // 先采音缓存，再连识别（避免等握手时丢开头）
    this.startMicGraph(ctx)

    const ws = new WebSocket(asrWsUrl())
    this.ws = ws
    ws.binaryType = 'arraybuffer'

    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(
        () => reject(new Error('连接语音识别超时')),
        15000,
      )
      ws.onmessage = (ev) => {
        if (typeof ev.data !== 'string') return
        let msg: AsrServerMessage
        try {
          msg = JSON.parse(ev.data) as AsrServerMessage
        } catch {
          return
        }
        if (msg.type === 'ready') {
          window.clearTimeout(timer)
          this.wsReady = true
          this.handlers.onReady?.()
          resolve()
          return
        }
        if (msg.type === 'error') {
          window.clearTimeout(timer)
          reject(new Error(msg.message || '识别服务错误'))
          return
        }
        this.handleAsrMessage(msg)
      }
      ws.onerror = () => {
        window.clearTimeout(timer)
        reject(new Error('无法连接语音识别服务（请确认后端 8787 已启动）'))
      }
      ws.onclose = () => {
        this.wsReady = false
      }
    })

    ws.onmessage = (ev) => {
      if (typeof ev.data !== 'string') return
      try {
        this.handleAsrMessage(JSON.parse(ev.data) as AsrServerMessage)
      } catch {
        /* ignore */
      }
    }

    this.sendTimer = window.setInterval(() => this.flushFrames(), 200)
    // 立刻冲一次已缓存音频
    this.flushFrames()
  }

  private handleAsrMessage(msg: AsrServerMessage) {
    if (msg.type === 'partial') {
      this.currentPartial = msg.text || ''
      this.handlers.onPartial?.(this.transcript)
      return
    }
    if (msg.type === 'final') {
      const piece = (msg.text || '').trim()
      if (piece) this.committed += piece
      this.currentPartial = ''
      this.handlers.onFinalSegment?.(piece)
      this.handlers.onPartial?.(this.transcript)
      return
    }
    if (msg.type === 'done') {
      this.handlers.onDone?.()
      return
    }
    if (msg.type === 'error') {
      this.handlers.onError?.(msg.message || '识别错误')
    }
  }

  async finish(): Promise<string> {
    // 再等一点尾音进入 ScriptProcessor
    await new Promise((r) => setTimeout(r, 250))

    if (this.wsReady && this.ws?.readyState === WebSocket.OPEN) {
      this.flushFrames()
      if (this.pcmBytes > 0) {
        const rest = this.takeBytes(this.pcmBytes)
        if (rest?.length) {
          const padded = new Uint8Array(Math.max(rest.length, FRAME_BYTES))
          padded.set(rest)
          try {
            this.ws.send(padded)
            this.bytesSent += padded.length
          } catch {
            /* ignore */
          }
        }
      }
      try {
        this.ws.send(JSON.stringify({ type: 'end' }))
      } catch {
        /* ignore */
      }

      await new Promise<void>((resolve) => {
        let settled = false
        const done = () => {
          if (settled) return
          settled = true
          resolve()
        }
        const timer = window.setTimeout(done, 3000)
        const prev = this.handlers.onDone
        this.handlers.onDone = () => {
          window.clearTimeout(timer)
          prev?.()
          done()
        }
        window.setTimeout(() => {
          if (this.transcript) done()
        }, 1200)
      })
    }

    const text = this.transcript
    const peak = this.peakLevel
    const sent = this.bytesSent
    await this.stop()

    if (peak < 0.008) {
      throw new Error(
        '几乎没检测到声音：请到系统设置确认默认麦克风，并允许浏览器使用麦克风',
      )
    }
    if (!text && sent < FRAME_BYTES) {
      throw new Error('音频未能发送到识别服务，请确认后端 8787 已启动')
    }
    return text
  }

  async cancel(): Promise<void> {
    await this.stop()
  }

  private async stop(): Promise<void> {
    this.closed = true
    this.wsReady = false
    if (this.sendTimer != null) {
      window.clearInterval(this.sendTimer)
      this.sendTimer = null
    }
    if (this.raf) cancelAnimationFrame(this.raf)
    try {
      this.processor?.disconnect()
      this.analyser?.disconnect()
      this.source?.disconnect()
      this.zeroGain?.disconnect()
    } catch {
      /* ignore */
    }
    this.processor = null
    this.analyser = null
    this.source = null
    this.zeroGain = null
    this.stream?.getTracks().forEach((t) => t.stop())
    this.stream = null
    try {
      await this.audioCtx?.close()
    } catch {
      /* ignore */
    }
    this.audioCtx = null
    try {
      this.ws?.close()
    } catch {
      /* ignore */
    }
    this.ws = null
    this.pcmChunks = []
    this.pcmBytes = 0
  }
}

export async function checkAsrStatus(): Promise<{ configured: boolean }> {
  try {
    const res = await fetch(
      import.meta.env.DEV
        ? 'http://127.0.0.1:8787/api/asr/status'
        : '/api/mawp/asr/status',
    )
    if (!res.ok) return { configured: false }
    const data = (await res.json()) as { configured?: boolean }
    return { configured: Boolean(data.configured) }
  } catch {
    return { configured: false }
  }
}
