import type { DeepSeekModelId } from '@/lib/deepseek'

/** DeepSeek 仅用于「写作链路」相关技能；WorkWings 9 Agent 编排在 backend */
export type DeepSeekSkillId = 'write' | 'req'

export interface DeepSeekSkill {
  id: DeepSeekSkillId
  label: string
  promptPrefix: string
  systemPrompt: string
  model: DeepSeekModelId
  deepThink: boolean
  wrapUserMessage: (topicOrText: string) => string
}

export const DEEPSEEK_SKILLS: Record<DeepSeekSkillId, DeepSeekSkill> = {
  write: {
    id: 'write',
    label: '帮我写作',
    promptPrefix: '帮我写：',
    model: 'deepseek-v4-flash',
    deepThink: false,
    systemPrompt: `你是「智流」写作助手（DeepSeek）。根据用户主题输出一篇可直接交付的完整中文文稿。

硬性格式：
1. 第一行必须是 Markdown 一级标题：# 文章标题（标题要贴合主题、有文采，不要用「关于xxx的作文」这种干巴标题）
2. 空一行后写正文；用短段落，必要时用 ## 小标题分节
3. 不要寒暄、不要解释你在做什么、不要输出「写作思路」；直接成稿
4. 信息不足时仍先给完整稿，文末用「还需要你补充：」列 2～4 条

语气自然、有画面感；适合右侧文档预览阅读。最终将作为 Word 云文档交付，不要提 Markdown。`,
    wrapUserMessage: (t) =>
      `请撰写完整文稿（第一行 # 标题，其后为正文段落），主题/要求如下：\n\n${t}`,
  },
  req: {
    id: 'req',
    label: '需求分析',
    promptPrefix: '帮我写需求文档，主题：',
    model: 'deepseek-v4-flash',
    deepThink: false,
    systemPrompt: `你是「智流」产品经理（DeepSeek）。输出完整可落地的 PRD（简体中文）。
用豆包式 Markdown：先给短标题与总述，再用 ## 分节；条目清晰，关键词加粗。
必须含：产品概述、用户与场景、功能需求、非功能需求、验收标准、里程碑、风险。
严格贴合用户主题；禁止换成无关样例。完整 WorkWings 9 Agent 交付请走 Studio/工作流。`,
    wrapUserMessage: (t) => `请输出完整产品需求文档，主题/描述：\n\n${t}`,
  },
}

export function getDeepSeekSkill(id: string | null | undefined): DeepSeekSkill | null {
  if (!id) return null
  return DEEPSEEK_SKILLS[id as DeepSeekSkillId] ?? null
}
