import type { StudioPageKind } from '@/lib/chat-intent'
import { chatWithDeepSeek, reasoningToSteps } from '@/lib/deepseek'

const STAGE_INSTRUCTION: Record<StudioPageKind, string> = {
  requirement: `你是资深产品经理。请严格根据用户目标输出完整可落地的需求文档（PRD）。
标题与正文必须贴合用户目标（例如用户要「贪吃蛇」就写贪吃蛇，禁止换成电商后台等无关样例）。
使用简体中文 Markdown：产品概述、功能需求（表格）、非功能需求、验收标准、下一步。`,
  architecture: `你是系统架构师。请严格根据用户目标设计架构方案与流程图。
禁止套用无关业务模板。使用简体中文 Markdown：技术选型、模块划分、架构图（ASCII）、关键接口、下一步。`,
  code: `你是全栈工程师。请严格根据用户目标生成可运行代码。
禁止生成无关业务代码。使用简体中文说明 + fenced code blocks。
若目标是小游戏、页面 Demo、前端交互：必须额外给出一份「可直接在浏览器运行」的完整单文件 HTML（含 CSS 与 JS），放在 \`\`\`html 代码块中，优先 Canvas/原生 JS，不要只给无法预览的框架骨架。
若目标是纯后端：说明本地启动步骤，并仍尽量给一段可演示的最小前端或 HTML 调试页。`,
  test: `你是测试工程师。请严格根据用户目标编写测试方案与用例报告。
禁止套用无关业务失败用例。使用简体中文 Markdown。`,
  deploy: `你是运维工程师。请严格根据用户目标给出部署上线方案。
禁止套用无关业务环境。使用简体中文 Markdown。`,
}

export async function generateStudioOutput(options: {
  kind: StudioPageKind
  source: string
  topic?: string
  signal?: AbortSignal
}): Promise<{ content: string; thinking: string[] }> {
  const { kind, source, topic, signal } = options
  const titleHint = topic?.trim() || source.slice(0, 40)
  const result = await chatWithDeepSeek({
    model: 'deepseek-v4-flash',
    deepThink: false,
    signal,
    messages: [
      {
        role: 'user',
        content: `${STAGE_INSTRUCTION[kind]}

项目主题：${titleHint}

用户原始需求：
${source}`,
      },
    ],
  })

  return {
    content: result.content,
    thinking: reasoningToSteps(result.reasoning),
  }
}
