/** 非 DeepSeek 技能执行器：PPT / 流程图 / 图像 / 视频 / 音乐 / 播客 / 研究 */

import PptxGenJS from 'pptxgenjs'
import type { FlowchartPayload } from '@/lib/flowchart'

export type ExternalSkillId =
  | 'ppt'
  | 'flowchart'
  | 'image'
  | 'video'
  | 'music'
  | 'podcast'
  | 'research'

export interface SkillRunResult {
  /** 写入对话的 Markdown/文本 */
  content: string
  /** 使用的能力说明 */
  provider: string
  /** 可选：触发浏览器下载 */
  download?: { filename: string; blob: Blob; mime: string }
  /** 图像技能：结构化图片，便于气泡内展示 */
  images?: Array<{
    url: string
    alt?: string
    width?: number
    height?: number
  }>
  /** 流程图技能 */
  flowchart?: FlowchartPayload
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function sanitizeTopic(raw: string) {
  return (
    raw
      .replace(
        /^(请生成 PPT[，,:：]?|PPT 主题[：:]?|请设计画面[，,:：]?|请深入研究[：:]?|请做一期播客[，,:：]?|请写短视频[，,:：]?|请创作歌曲[，,:：]?|请生成流程图[，,:：]?|流程图[：:]?|流程主题[：:]?)/i,
        '',
      )
      .trim() || '未命名主题'
  )
}

/** 流程图：DeepSeek 出 JSON，前端渲染/编辑 */
export async function runFlowchartSkill(
  topicRaw: string,
  opts?: { files?: File[]; signal?: AbortSignal },
): Promise<SkillRunResult> {
  const { generateFlowchart } = await import('@/lib/flowchart-gen')
  const topic = sanitizeTopic(topicRaw)
  const doc = await generateFlowchart({
    topic,
    files: opts?.files,
    signal: opts?.signal,
  })

  return {
    provider: 'DeepSeek V4 Flash · 流程图',
    flowchart: doc,
    content: [
      `已生成流程图「**${doc.title}**」。`,
      '',
      `- 节点：${doc.nodes.length} · 连线：${doc.edges.length}`,
      doc.sourceHint ? `- 材料：${doc.sourceHint}` : '',
      '',
      '点击卡片可打开编辑器：拖拽节点、改文案、增删步骤；可下载 Mermaid / SVG / JSON。',
      '',
      '可以说「加一个审批分支」或继续上传文档再生成一版。',
    ]
      .filter(Boolean)
      .join('\n'),
  }
}

/** 真 PPT 文件（pptxgenjs，不走 DeepSeek） */
export async function runPptSkill(topicRaw: string): Promise<SkillRunResult> {
  const topic = sanitizeTopic(topicRaw)
  const pptx = new PptxGenJS()
  pptx.author = '智流 MAWP'
  pptx.title = topic

  const slides: Array<{ title: string; bullets: string[] }> = [
    { title: topic, bullets: ['智流 MAWP 自动生成', new Date().toLocaleString('zh-CN'), '可在 PowerPoint / WPS 中继续编辑'] },
    { title: '目录', bullets: ['背景与目标', '方案概述', '关键要点', '实施路径', '风险与下一步'] },
    { title: '背景与目标', bullets: [`围绕「${topic}」展开`, '明确业务价值与成功标准', '对齐干系人预期'] },
    { title: '方案概述', bullets: ['整体思路一句话说明', '核心模块拆分', '与现有系统的关系'] },
    { title: '关键要点 A', bullets: ['能力点 1', '能力点 2', '能力点 3'] },
    { title: '关键要点 B', bullets: ['数据与指标', '体验与流程', '安全与合规'] },
    { title: '实施路径', bullets: ['P0：最小可用', 'P1：增强体验', 'P2：规模化'] },
    { title: '风险与缓解', bullets: ['技术风险 → 预研/灰度', '进度风险 → 里程碑检查', '依赖风险 → 备选方案'] },
    { title: '下一步', bullets: ['确认范围', '排期与资源', '启动第一迭代', 'Q & A'] },
  ]

  slides.forEach((s, i) => {
    const slide = pptx.addSlide()
    slide.addText(s.title, {
      x: 0.5,
      y: i === 0 ? 2.2 : 0.4,
      w: 9,
      h: 0.8,
      fontSize: i === 0 ? 32 : 24,
      bold: true,
      color: '1F2329',
    })
    if (i === 0) {
      slide.addText(s.bullets.join('\n'), {
        x: 0.5,
        y: 3.2,
        w: 9,
        h: 1.5,
        fontSize: 14,
        color: '4E5969',
      })
    } else {
      slide.addText(s.bullets.map((b) => ({ text: b, options: { bullet: true } })), {
        x: 0.6,
        y: 1.4,
        w: 8.8,
        h: 4,
        fontSize: 16,
        color: '3D4654',
        paraSpacingAfter: 10,
      })
    }
  })

  const blob = (await pptx.write({ outputType: 'blob' })) as Blob
  const filename = `${topic.slice(0, 24) || '智流演示'}.pptx`
  downloadBlob(filename, blob)

  return {
    provider: 'pptxgenjs（本地生成 .pptx，非 DeepSeek）',
    content: [
      `# PPT 已生成：${topic}`,
      '',
      `已下载 **${filename}**（共 ${slides.length} 页）。`,
      '',
      '## 页面结构',
      ...slides.map((s, i) => `${i + 1}. ${s.title}`),
      '',
      '> 说明：DeepSeek 不负责出 PPT 文件；本功能用演示文稿引擎直接生成可编辑的 `.pptx`。',
    ].join('\n'),
    download: {
      filename,
      blob,
      mime: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    },
  }
}

/** 图像：Pollinations Flux，自动识别尺寸/风格并预检 */
export async function runImageSkill(topicRaw: string): Promise<SkillRunResult> {
  const { generateImageFromTopic } = await import('@/lib/image-gen')
  const result = await generateImageFromTopic(topicRaw)

  return {
    provider: result.provider,
    content: [
      `已根据「**${result.topic}**」生成图像。`,
      '',
      `- 尺寸：${result.sizeLabel}（${result.width}×${result.height}）`,
      `- 风格：${result.styleHint}`,
      `- 模型：Flux`,
      '',
      '## 提示词',
      '```',
      result.prompt,
      '```',
      '',
      '可以说「再画一张更写实的」或「改成竖图」继续调整。',
    ].join('\n'),
    images: [
      {
        url: result.url,
        alt: result.topic,
        width: result.width,
        height: result.height,
      },
    ],
  }
}

/** 视频：产出可投喂视频模型的分镜包（非 DeepSeek） */
export async function runVideoSkill(topicRaw: string): Promise<SkillRunResult> {
  const topic = sanitizeTopic(topicRaw)
  const text = [
    `# 短视频分镜包 · ${topic}`,
    '',
    'provider: local-storyboard (非 DeepSeek)',
    '',
    '## 镜头表',
    '| 镜号 | 时长 | 画面 | 旁白 |',
    '|---|---|---|---|',
    `| 1 | 3s | 标题卡「${topic}」| 开场钩子 |`,
    `| 2 | 5s | 主体特写 | 点明痛点 |`,
    `| 3 | 8s | 方案演示 | 展示核心能力 |`,
    `| 4 | 5s | 结果对比 | 强调价值 |`,
    `| 5 | 4s | Logo/CTA | 引导行动 |`,
    '',
    '## 文生视频英文提示（可灵/即梦）',
    '```',
    `A vertical short video about ${topic}, cinematic, 9:16, dynamic camera`,
    '```',
    '',
    '配置 `VIDEO_API_KEY` 后可改为真实成片接口。',
  ].join('\n')
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const filename = `video-${topic.slice(0, 16)}.md`
  downloadBlob(filename, blob)
  return {
    provider: '本地分镜包（可接可灵/即梦）',
    content: text,
    download: { filename, blob, mime: 'text/markdown' },
  }
}

/** 音乐：歌词 + Suno style（非 DeepSeek） */
export async function runMusicSkill(topicRaw: string): Promise<SkillRunResult> {
  const topic = sanitizeTopic(topicRaw)
  const text = [
    `# 歌曲方案 · ${topic}`,
    '',
    'provider: local-lyric-kit (非 DeepSeek)',
    '',
    '## Style Prompt（Suno）',
    '```',
    `pop, emotional, mid-tempo, clear vocals, about ${topic}`,
    '```',
    '',
    '## 歌词草稿',
    '【主歌】',
    `关于${topic}的故事缓缓展开`,
    '灯光落下，心跳跟着节拍走',
    '',
    '【副歌】',
    `我们为了${topic}不怕回头`,
    '唱给此刻，也唱给以后',
    '',
    '配置音乐 API 后可直接出音频。',
  ].join('\n')
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const filename = `music-${topic.slice(0, 16)}.md`
  downloadBlob(filename, blob)
  return {
    provider: '本地词曲包（可接 Suno）',
    content: text,
    download: { filename, blob, mime: 'text/markdown' },
  }
}

/** 播客：模板口播 + 浏览器 TTS 试听（非 DeepSeek） */
export async function runPodcastSkill(topicRaw: string): Promise<SkillRunResult> {
  const topic = sanitizeTopic(topicRaw)
  const script = [
    `大家好，欢迎收听智流播客。`,
    `今天我们聊的主题是：${topic}。`,
    `先用一分钟讲清楚它是什么、为什么重要。`,
    `接着给出三个可执行建议，方便你马上落地。`,
    `感谢收听，我们下期见。`,
  ]
  const content = [
    `# AI 播客 · ${topic}`,
    '',
    'provider: Web Speech TTS（非 DeepSeek）',
    '',
    '## 口播稿',
    ...script.map((line, i) => `**${i % 2 === 0 ? 'A' : 'B'}**：${line}`),
    '',
    '> 已尝试用系统语音朗读；若无声音请检查浏览器是否允许语音合成。',
  ].join('\n')

  try {
    const utter = new SpeechSynthesisUtterance(script.join(' '))
    utter.lang = 'zh-CN'
    utter.rate = 1
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utter)
  } catch {
    /* ignore */
  }

  return { provider: 'Web Speech TTS', content }
}

/** 研究：维基摘要（非 DeepSeek） */
export async function runResearchSkill(topicRaw: string): Promise<SkillRunResult> {
  const topic = sanitizeTopic(topicRaw)
  const title = encodeURIComponent(topic)
  let summary = ''
  let url = ''
  try {
    const res = await fetch(
      `https://zh.wikipedia.org/api/rest_v1/page/summary/${title}`,
    )
    if (res.ok) {
      const data = (await res.json()) as {
        extract?: string
        content_urls?: { desktop?: { page?: string } }
        title?: string
      }
      summary = data.extract || ''
      url = data.content_urls?.desktop?.page || ''
    }
  } catch {
    /* ignore */
  }

  if (!summary) {
    summary =
      `暂未在维基百科匹配到「${topic}」的条目摘要。请换更短的关键词重试，或配置搜索 API 做深度检索。`
  }

  return {
    provider: 'Wikipedia REST（非 DeepSeek）',
    content: [
      `# 深入研究：${topic}`,
      '',
      '## 资料摘要',
      summary,
      url ? `\n来源：${url}` : '',
      '',
      '## 建议下一步',
      '- 核对一手资料与最新数据',
      '- 对比 2–3 种方案的成本/风险',
      '- 输出可执行的落地清单',
      '',
      '> 本技能走维基检索，**不调用 DeepSeek**。完整 WorkWings 9 Agent 编排请走 Studio / 工作流运行。',
    ].join('\n'),
  }
}

export async function runExternalSkill(
  id: ExternalSkillId,
  topic: string,
  opts?: { files?: File[]; signal?: AbortSignal },
): Promise<SkillRunResult> {
  switch (id) {
    case 'ppt':
      return runPptSkill(topic)
    case 'flowchart':
      return runFlowchartSkill(topic, opts)
    case 'image':
      return runImageSkill(topic)
    case 'video':
      return runVideoSkill(topic)
    case 'music':
      return runMusicSkill(topic)
    case 'podcast':
      return runPodcastSkill(topic)
    case 'research':
      return runResearchSkill(topic)
    default:
      throw new Error(`未知技能: ${id}`)
  }
}

export const EXTERNAL_SKILL_META: Record<
  ExternalSkillId,
  { label: string; promptPrefix: string; providerHint: string }
> = {
  ppt: {
    label: 'PPT 生成',
    promptPrefix: 'PPT 主题：',
    providerHint: 'pptxgenjs',
  },
  flowchart: {
    label: '流程图',
    promptPrefix: '流程主题：',
    providerHint: 'DeepSeek V4 Flash',
  },
  image: {
    label: '图像生成',
    promptPrefix: '画面主题：',
    providerHint: 'Pollinations Flux',
  },
  video: {
    label: '视频生成',
    promptPrefix: '视频主题：',
    providerHint: '分镜包',
  },
  music: {
    label: '音乐生成',
    promptPrefix: '歌曲主题：',
    providerHint: '词曲包',
  },
  podcast: {
    label: 'AI 播客',
    promptPrefix: '播客主题：',
    providerHint: 'Web Speech',
  },
  research: {
    label: '深入研究',
    promptPrefix: '研究课题：',
    providerHint: 'Wikipedia',
  },
}
