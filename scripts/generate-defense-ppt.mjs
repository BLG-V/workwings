/**
 * 智流 AgentFlow 答辩 PPT · 41 页
 * 视觉：云雾浅昼「杂志纸感」——暗色扉页节奏 + 大字号层级 + 不对称版式 + 照片位
 * 避免：满页同款卡片 / 塑料厚阴影 / 纯白单调
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import PptxGenJS from 'pptxgenjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')
const OUT = path.join(ROOT, 'docs', 'course-submit', '智流AgentFlow-答辩-新版.pptx')
const DESKTOP = process.env.USERPROFILE
  ? path.join(process.env.USERPROFILE, 'Desktop', '智流AgentFlow-答辩-新版.pptx')
  : ''

const T = {
  paper: 'F4F7FA',
  wash: 'E8F0F7',
  mist: 'D9E7F2',
  blue: '7BA8C9',
  blueDeep: '4A6F8F',
  ink: '1E2A36',
  soft: '4A5C6A',
  mute: '7A8B99',
  line: 'C9D8E6',
  white: 'FFFFFF',
  glow: 'A8C8DE',
  accent: '5B9BC4',
}

const F = 'Microsoft YaHei'
const FE = 'Calibri'
const TOTAL = 41
let N = 0

const pptx = new PptxGenJS()
pptx.author = '智流 AgentFlow · 四组'
pptx.title = '智流 AgentFlow 答辩'
pptx.layout = 'LAYOUT_WIDE'

function tick() {
  N += 1
  return N
}

/** 大气纸感底：色带洗 + 柔光 + 细线，不做点阵塑料 */
function paperBg(s) {
  s.addShape(pptx.shapes.RECTANGLE, {
    x: 0, y: 0, w: '100%', h: '100%',
    fill: { color: T.paper },
  })
  s.addShape(pptx.shapes.RECTANGLE, {
    x: 0, y: 0, w: '100%', h: 0.08,
    fill: { color: T.blueDeep },
  })
  s.addShape(pptx.shapes.OVAL, {
    x: 8.8, y: -2.4, w: 7, h: 6.5,
    fill: { color: T.wash, transparency: 35 },
    line: { transparency: 100 },
  })
  s.addShape(pptx.shapes.OVAL, {
    x: -2.5, y: 4.5, w: 6, h: 5,
    fill: { color: T.mist, transparency: 55 },
    line: { transparency: 100 },
  })
  s.addShape(pptx.shapes.RECTANGLE, {
    x: 0, y: 6.95, w: '100%', h: 0.55,
    fill: { color: T.wash, transparency: 40 },
  })
}

/** 浅色章节扉页（不用深色） */
function chapterBg(s) {
  paperBg(s)
  s.addShape(pptx.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.1, h: '100%',
    fill: { color: T.blueDeep },
  })
  s.addShape(pptx.shapes.OVAL, {
    x: 8.5, y: -1.5, w: 7, h: 6,
    fill: { color: T.mist, transparency: 40 },
    line: { transparency: 100 },
  })
  washBlock(s, 0.55, 1.4, 12.2, 4.9)
}

function footer(s) {
  s.addText('智流 MAWP', {
    x: 0.55, y: 7.1, w: 4, h: 0.22,
    fontSize: 9, color: T.mute, fontFace: F,
  })
  s.addText(`${String(N).padStart(2, '0')}  /  ${TOTAL}`, {
    x: 10.5, y: 7.1, w: 2.3, h: 0.22,
    fontSize: 9, color: T.mute, fontFace: FE, align: 'right',
  })
}

function panel(s, x, y, w, h, opts = {}) {
  s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h,
    fill: { color: opts.fill || T.white },
    line: { color: opts.line || T.line, width: opts.lw ?? 0.75 },
    rectRadius: opts.r ?? 0.06,
  })
}

function washBlock(s, x, y, w, h) {
  s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h,
    fill: { color: T.wash },
    line: { color: T.wash },
    rectRadius: 0.06,
  })
}

function accentBar(s, x, y, h) {
  s.addShape(pptx.shapes.RECTANGLE, {
    x, y, w: 0.05, h,
    fill: { color: T.blueDeep },
  })
}

function pageHead(s, en, zh, sub) {
  s.addText(en.toUpperCase(), {
    x: 0.7, y: 0.35, w: 8, h: 0.24,
    fontSize: 10, bold: true, color: T.blue, fontFace: FE, charSpacing: 3,
  })
  accentBar(s, 0.7, 0.7, 0.55)
  s.addText(zh, {
    x: 0.95, y: 0.68, w: 10, h: 0.5,
    fontSize: 28, bold: true, color: T.ink, fontFace: F,
  })
  if (sub) {
    s.addText(sub, {
      x: 0.95, y: 1.25, w: 11, h: 0.28,
      fontSize: 12, color: T.mute, fontFace: F,
    })
  }
}

function partSlide(n, zh, en, blurb) {
  const s = pptx.addSlide()
  tick()
  chapterBg(s)
  s.addText(String(n).padStart(2, '0'), {
    x: 1.0, y: 1.85, w: 4, h: 1.3,
    fontSize: 88, bold: true, color: T.mist, fontFace: FE,
  })
  s.addText(`PART ${n}`, {
    x: 1.0, y: 3.2, w: 8, h: 0.3,
    fontSize: 12, bold: true, color: T.blue, fontFace: FE, charSpacing: 4,
  })
  s.addText(zh, {
    x: 1.0, y: 3.6, w: 11, h: 0.7,
    fontSize: 38, bold: true, color: T.ink, fontFace: F,
  })
  s.addText(en, {
    x: 1.0, y: 4.4, w: 11, h: 0.35,
    fontSize: 14, color: T.soft, fontFace: FE,
  })
  s.addShape(pptx.shapes.RECTANGLE, {
    x: 1.0, y: 4.95, w: 1.6, h: 0.02,
    fill: { color: T.blueDeep },
  })
  s.addText(blurb, {
    x: 1.0, y: 5.2, w: 10, h: 0.4,
    fontSize: 13, color: T.mute, fontFace: F,
  })
  footer(s)
}

function photoSlot(s, x, y, w, h) {
  s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h,
    fill: { color: T.mist },
    line: { color: T.blue, width: 1 },
    rectRadius: 0.08,
  })
  // 人像示意
  s.addShape(pptx.shapes.OVAL, {
    x: x + w * 0.32, y: y + h * 0.18, w: w * 0.36, h: w * 0.36,
    fill: { color: T.blue, transparency: 55 },
    line: { transparency: 100 },
  })
  s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: x + w * 0.22, y: y + h * 0.52, w: w * 0.56, h: h * 0.28,
    fill: { color: T.blue, transparency: 65 },
    line: { transparency: 100 },
    rectRadius: 0.12,
  })
  s.addText('PHOTO', {
    x, y: y + h - 0.32, w, h: 0.22,
    fontSize: 8, color: T.blueDeep, align: 'center', fontFace: FE, bold: true,
  })
}

// ═══════════ 1 封面：浅色不对称 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  washBlock(s, 0.4, 0.4, 4.0, 6.5)
  s.addShape(pptx.shapes.RECTANGLE, {
    x: 4.4, y: 0.4, w: 0.05, h: 6.5,
    fill: { color: T.blueDeep },
  })
  s.addText('2508A', {
    x: 0.7, y: 0.75, w: 3.4, h: 0.3,
    fontSize: 11, color: T.blue, fontFace: FE, bold: true, charSpacing: 3,
  })
  s.addText('智流', {
    x: 0.7, y: 2.3, w: 3.5, h: 0.7,
    fontSize: 42, bold: true, color: T.ink, fontFace: F,
  })
  s.addText('AgentFlow', {
    x: 0.7, y: 3.05, w: 3.5, h: 0.55,
    fontSize: 24, bold: true, color: T.blueDeep, fontFace: FE,
  })
  s.addText('MAWP', {
    x: 0.7, y: 3.65, w: 3.5, h: 0.35,
    fontSize: 14, color: T.mute, fontFace: FE, charSpacing: 4,
  })
  s.addShape(pptx.shapes.RECTANGLE, {
    x: 0.7, y: 4.25, w: 1.2, h: 0.02,
    fill: { color: T.blueDeep },
  })
  s.addText('四组答辩  ·  2026.08', {
    x: 0.7, y: 5.9, w: 3.4, h: 0.4,
    fontSize: 12, color: T.mute, fontFace: F,
  })

  s.addText('多智能体工作流平台', {
    x: 4.9, y: 2.4, w: 7.8, h: 0.7,
    fontSize: 28, bold: true, color: T.ink, fontFace: F,
  })
  s.addText('把「对话意图」编排成「可验收工程交付」', {
    x: 4.9, y: 3.2, w: 7.5, h: 0.45,
    fontSize: 15, color: T.soft, fontFace: F,
  })
  ;['智能编排', '可验收交付', '过程可复现'].forEach((t, i) => {
    const x = 4.9 + i * 2.5
    washBlock(s, x, 4.2, 2.25, 0.7)
    s.addText(t, {
      x, y: 4.35, w: 2.25, h: 0.4,
      fontSize: 12, bold: true, color: T.blueDeep, align: 'center', fontFace: F,
    })
  })
  s.addText('云计算 2508A  ·  答辩汇报', {
    x: 4.9, y: 5.5, w: 7, h: 0.35,
    fontSize: 12, color: T.mute, fontFace: F,
  })
}

// ═══════════ 2 目录：杂志编号列表 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Contents', '目录')
  const toc = [
    ['01', '团队介绍', '成员 · 分工 · 协作'],
    ['02', '项目背景', '痛点 · 定位 · 价值'],
    ['03', '系统架构', '分层 · 技术栈 · 主链'],
    ['04', '核心功能', '对话 · Studio · 工作流'],
    ['05', 'AI 核心能力', '模型 · 引擎 · 记忆'],
    ['06', '测试与部署', '质量 · 本地运行'],
    ['07', '总结与展望', '创新 · 规划 · 致谢'],
  ]
  toc.forEach((t, i) => {
    const y = 1.75 + i * 0.7
    s.addShape(pptx.shapes.RECTANGLE, {
      x: 0.7, y: y + 0.55, w: 11.9, h: 0.008,
      fill: { color: T.line },
    })
    s.addText(t[0], {
      x: 0.7, y, w: 1.2, h: 0.5,
      fontSize: 22, bold: true, color: T.blue, fontFace: FE,
    })
    s.addText(t[1], {
      x: 2.1, y, w: 4, h: 0.5,
      fontSize: 18, bold: true, color: T.ink, fontFace: F,
    })
    s.addText(t[2], {
      x: 7.5, y, w: 5, h: 0.5,
      fontSize: 13, color: T.mute, fontFace: F, align: 'right',
    })
  })
  footer(s)
}

partSlide(1, '团队介绍', 'TEAM INTRODUCTION', '成员、分工与协作方式')

// ═══════════ 4 团队 + 照片位 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Team', '四组 · 智流项目组', '请在 PHOTO 区域粘贴成员照片')
  const team = [
    ['李子玉', '项目经理', 'PM', '统筹 · 需求 · 进度'],
    ['王振同', '后端开发', 'BE', '内核 · API · 引擎'],
    ['李铭宇', '全栈开发', 'FS', 'Studio · 工作区'],
    ['孙浩铭', 'AI 工程', 'AI', 'Agent · 模型策略'],
  ]
  const cw = 2.9
  const gap = 0.3
  const start = (13.333 - team.length * cw - (team.length - 1) * gap) / 2
  team.forEach((m, i) => {
    const x = start + i * (cw + gap)
    panel(s, x, 1.85, cw, 4.85)
    photoSlot(s, x + 0.25, 2.1, cw - 0.5, 2.35)
    washBlock(s, x + 0.25, 4.6, cw - 0.5, 0.38)
    s.addText(m[2], {
      x: x + 0.25, y: 4.65, w: cw - 0.5, h: 0.28,
      fontSize: 11, bold: true, color: T.blueDeep, align: 'center', fontFace: FE,
    })
    s.addText(m[0], {
      x: x + 0.1, y: 5.15, w: cw - 0.2, h: 0.4,
      fontSize: 17, bold: true, color: T.ink, align: 'center', fontFace: F,
    })
    s.addText(m[1], {
      x: x + 0.1, y: 5.55, w: cw - 0.2, h: 0.28,
      fontSize: 11, color: T.soft, align: 'center', fontFace: F,
    })
    s.addText(m[3], {
      x: x + 0.1, y: 5.95, w: cw - 0.2, h: 0.35,
      fontSize: 10, color: T.mute, align: 'center', fontFace: F,
    })
  })
  footer(s)
}

// ═══════════ 5 协作 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Collaboration', '协作模式')
  ;[
    ['01', 'Deliver 主链', 'Planner → Requirement → Coding → Frontend → Testing ↔ Debug → Review → Ship'],
    ['02', '角色分工', '前端智流 UI · 后端 MAWP 内核 · 全栈 Studio · AI Agent 策略'],
    ['03', '工程约束', '本地可跑 · 人工审批闸门 · 禁止自动 push · Run 可观测'],
  ].forEach((row, i) => {
    const y = 1.85 + i * 1.55
    washBlock(s, 0.7, y, 1.4, 1.3)
    s.addText(row[0], {
      x: 0.7, y: y + 0.4, w: 1.4, h: 0.5,
      fontSize: 24, bold: true, color: T.blueDeep, align: 'center', fontFace: FE,
    })
    panel(s, 2.3, y, 10.3, 1.3)
    s.addText(row[1], {
      x: 2.6, y: y + 0.25, w: 9.7, h: 0.35,
      fontSize: 16, bold: true, color: T.ink, fontFace: F,
    })
    s.addText(row[2], {
      x: 2.6, y: y + 0.7, w: 9.7, h: 0.4,
      fontSize: 12, color: T.soft, fontFace: F,
    })
  })
  footer(s)
}

partSlide(2, '项目背景', 'PROJECT BACKGROUND', '痛点、定位与业务价值')

// ═══════════ 7 趋势痛点 左右分栏 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Context', '行业趋势与痛点')
  washBlock(s, 0.7, 1.8, 5.7, 4.8)
  s.addText('TRENDS', {
    x: 1.0, y: 2.05, w: 5, h: 0.28,
    fontSize: 11, bold: true, color: T.blue, fontFace: FE, charSpacing: 2,
  })
  s.addText('行业趋势', {
    x: 1.0, y: 2.4, w: 5, h: 0.4,
    fontSize: 20, bold: true, color: T.ink, fontFace: F,
  })
  ;[
    '大模型进入 Agent + 工具 + 工作流阶段',
    '企业需要可编排、可验收的交付平台',
    '从长对话写代码走向工程化流水线',
  ].forEach((t, i) => {
    s.addShape(pptx.shapes.OVAL, {
      x: 1.0, y: 3.15 + i * 0.85, w: 0.14, h: 0.14,
      fill: { color: T.blue },
    })
    s.addText(t, {
      x: 1.35, y: 3.05 + i * 0.85, w: 4.7, h: 0.7,
      fontSize: 13, color: T.soft, fontFace: F,
    })
  })

  panel(s, 6.7, 1.8, 5.9, 4.8)
  s.addText('PAINS', {
    x: 7.0, y: 2.05, w: 5, h: 0.28,
    fontSize: 11, bold: true, color: T.blueDeep, fontFace: FE, charSpacing: 2,
  })
  s.addText('企业痛点', {
    x: 7.0, y: 2.4, w: 5, h: 0.4,
    fontSize: 20, bold: true, color: T.ink, fontFace: F,
  })
  ;[
    '上下文腐烂，质量无门禁',
    '过程难复现，交付不可控',
    '成本盲区，空壳「假绿」难发现',
  ].forEach((t, i) => {
    s.addText(`${i + 1}`, {
      x: 7.0, y: 3.15 + i * 0.85, w: 0.4, h: 0.4,
      fontSize: 18, bold: true, color: T.blue, fontFace: FE,
    })
    s.addText(t, {
      x: 7.5, y: 3.15 + i * 0.85, w: 4.7, h: 0.55,
      fontSize: 13, color: T.soft, fontFace: F,
    })
  })
  footer(s)
}

// ═══════════ 8 定位 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Positioning', '产品定位')
  // 大定位块
  s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 0.7, y: 1.85, w: 12, h: 1.8,
    fill: { color: T.wash },
    rectRadius: 0.08,
  })
  s.addText('一句话定位', {
    x: 1.1, y: 2.1, w: 11, h: 0.3,
    fontSize: 11, color: T.blue, fontFace: F, bold: true,
  })
  s.addText('把「对话意图」编排成「可验收工程交付」的多 Agent 工作流平台', {
    x: 1.1, y: 2.55, w: 11, h: 0.7,
    fontSize: 20, bold: true, color: T.ink, fontFace: F,
  })
  ;[
    ['目标用户', '实训演示 · 课程答辩 · 本地交付团队'],
    ['核心能力', '对话技能 · Studio · 八 Agent Deliver'],
    ['差异化', '真实冒烟 · 人工闸门 · 用户分桶'],
  ].forEach((c, i) => {
    const x = 0.7 + i * 4.1
    panel(s, x, 4.0, 3.9, 2.4)
    s.addText(c[0], {
      x: x + 0.25, y: 4.3, w: 3.4, h: 0.4,
      fontSize: 14, bold: true, color: T.blueDeep, fontFace: F,
    })
    s.addText(c[1], {
      x: x + 0.25, y: 4.9, w: 3.4, h: 1.0,
      fontSize: 13, color: T.soft, fontFace: F,
    })
  })
  footer(s)
}

// ═══════════ 9 价值 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Value', '业务价值')
  // 闭环
  ;['需求', '编排', '交付', '验收'].forEach((n, i) => {
    const x = 1.3 + i * 2.9
    s.addShape(pptx.shapes.OVAL, {
      x: x + 0.55, y: 1.9, w: 0.7, h: 0.7,
      fill: { color: i === 3 ? T.blueDeep : T.blue },
    })
    s.addText(n, {
      x: x + 0.55, y: 2.05, w: 0.7, h: 0.4,
      fontSize: 12, bold: true, color: T.white, align: 'center', fontFace: F,
    })
    if (i < 3) {
      s.addShape(pptx.shapes.RIGHT_ARROW, {
        x: x + 1.45, y: 2.12, w: 0.4, h: 0.25,
        fill: { color: T.mist },
        line: { color: T.mist },
      })
    }
  })
  ;[
    ['提效', '对话技能 + 编排一键交付'],
    ['降本', 'Flash / Pro 分档，成本可观测'],
    ['可控', '人工审批 · 禁止自动 push'],
    ['复用', 'YAML 固化 · workspaces 分期'],
  ].forEach((v, i) => {
    const x = 0.7 + (i % 2) * 6.2
    const y = 3.1 + Math.floor(i / 2) * 1.7
    panel(s, x, y, 5.95, 1.45)
    s.addText(v[0], {
      x: x + 0.35, y: y + 0.3, w: 1.6, h: 0.55,
      fontSize: 24, bold: true, color: T.blueDeep, fontFace: F,
    })
    s.addText(v[1], {
      x: x + 2.1, y: y + 0.4, w: 3.5, h: 0.55,
      fontSize: 13, color: T.soft, fontFace: F, valign: 'middle',
    })
  })
  footer(s)
}

partSlide(3, '系统架构', 'ARCHITECTURE', '分层架构、技术栈与核心流程')

// ═══════════ 11 分层 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Architecture', '整体架构')
  const layers = [
    ['用户层', '智流 React UI', '对话 · Studio · 编排 · 高级项目', false],
    ['接入层', 'Vite 智能代理', '/api/mawp · deepseek · bocha', false],
    ['服务层', 'MAWP FastAPI', 'YAML · 八 Agent · SelfHeal · Run', true],
    ['模型层', 'DeepSeek V4', 'Flash / Pro 分档路由', false],
    ['数据层', '本地存储', '.mawp Run · workspaces · 分桶', false],
  ]
  layers.forEach((L, i) => {
    const y = 1.75 + i * 0.95
    if (L[3]) {
      s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
        x: 1.2, y, w: 11.2, h: 0.82,
        fill: { color: T.wash },
        rectRadius: 0.06,
      })
      s.addText(L[0], { x: 1.5, y: y + 0.2, w: 1.6, h: 0.4, fontSize: 13, bold: true, color: T.blueDeep, fontFace: F })
      s.addText(L[1], { x: 3.3, y: y + 0.1, w: 3.5, h: 0.3, fontSize: 14, bold: true, color: T.ink, fontFace: F })
      s.addText(L[2], { x: 3.3, y: y + 0.42, w: 8.5, h: 0.3, fontSize: 11, color: T.mute, fontFace: F })
    } else {
      panel(s, 1.2, y, 11.2, 0.82)
      s.addText(L[0], { x: 1.5, y: y + 0.2, w: 1.6, h: 0.4, fontSize: 13, bold: true, color: T.blueDeep, fontFace: F })
      s.addText(L[1], { x: 3.3, y: y + 0.1, w: 3.5, h: 0.3, fontSize: 14, bold: true, color: T.ink, fontFace: F })
      s.addText(L[2], { x: 3.3, y: y + 0.42, w: 8.5, h: 0.3, fontSize: 11, color: T.mute, fontFace: F })
    }
  })
  footer(s)
}

// ═══════════ 12 技术栈 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Stack', '关键技术清单')
  ;[
    ['前端 Frontend', ['React 19', 'Vite', 'Tailwind', 'xyflow']],
    ['后端 Backend', ['FastAPI', 'YAML Engine', 'SelfHeal', 'Run 存储']],
    ['模型 & 扩展', ['DeepSeek Pro', 'DeepSeek Flash', 'Bocha', 'ASR']],
  ].forEach((col, i) => {
    const x = 0.7 + i * 4.15
    washBlock(s, x, 1.8, 3.95, 0.55)
    s.addText(col[0], {
      x, y: 1.9, w: 3.95, h: 0.35,
      fontSize: 13, bold: true, color: T.blueDeep, align: 'center', fontFace: F,
    })
    col[1].forEach((tag, j) => {
      panel(s, x, 2.55 + j * 0.95, 3.95, 0.8)
      s.addText(tag, {
        x, y: 2.7 + j * 0.95, w: 3.95, h: 0.45,
        fontSize: 14, color: T.ink, align: 'center', fontFace: F,
      })
    })
  })
  footer(s)
}

// ═══════════ 13 业务架构 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Business', '业务架构')
  s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 4.0, y: 2.4, w: 5.3, h: 1.5,
    fill: { color: T.wash },
    rectRadius: 0.1,
  })
  s.addText('智流大脑', {
    x: 4.0, y: 2.7, w: 5.3, h: 0.45,
    fontSize: 22, bold: true, color: T.ink, align: 'center', fontFace: F,
  })
  s.addText('AgentFlow Core  ·  MAWP', {
    x: 4.0, y: 3.25, w: 5.3, h: 0.35,
    fontSize: 12, color: T.blue, align: 'center', fontFace: FE,
  })
  ;[
    ['智能对话', 0.9, 2.0],
    ['工作台', 9.3, 2.0],
    ['工作流', 0.9, 5.0],
    ['高级项目', 9.3, 5.0],
  ].forEach(([lab, x, y]) => {
    panel(s, x, y, 3.1, 1.15)
    s.addText(lab, {
      x, y: y + 0.35, w: 3.1, h: 0.45,
      fontSize: 15, bold: true, color: T.ink, align: 'center', fontFace: F,
    })
  })
  footer(s)
}

// ═══════════ 14 流程时间轴 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Loop', '核心流程链路')
  s.addShape(pptx.shapes.RECTANGLE, {
    x: 0.9, y: 3.55, w: 11.5, h: 0.04,
    fill: { color: T.mist },
  })
  const steps = [
    ['01', '输入', '目标 / SRS'],
    ['02', '规划', 'Planner'],
    ['03', '实现', 'Code + FE'],
    ['04', '回环', 'Test↔Debug'],
    ['05', '审查', 'Review'],
    ['06', '交付', 'Ship'],
  ]
  steps.forEach((st, i) => {
    const x = 0.85 + i * 2.05
    const up = i % 2 === 0
    const y = up ? 2.0 : 4.0
    s.addShape(pptx.shapes.OVAL, {
      x: x + 0.55, y: 3.35, w: 0.45, h: 0.45,
      fill: { color: T.blueDeep },
    })
    s.addText(st[0], {
      x: x + 0.55, y: 3.42, w: 0.45, h: 0.32,
      fontSize: 9, bold: true, color: T.white, align: 'center', fontFace: FE,
    })
    panel(s, x, y, 1.8, 1.15)
    s.addText(st[1], {
      x, y: y + 0.2, w: 1.8, h: 0.35,
      fontSize: 14, bold: true, color: T.ink, align: 'center', fontFace: F,
    })
    s.addText(st[2], {
      x, y: y + 0.6, w: 1.8, h: 0.35,
      fontSize: 11, color: T.mute, align: 'center', fontFace: F,
    })
  })
  footer(s)
}

// ═══════════ 15 功能概览 2x3 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Overview', '重点功能概览')
  ;[
    ['01', '智能对话', '技能轨 · 多模态 · 流式'],
    ['02', '工作台', '五阶段 Studio · 大项目'],
    ['03', '工作流', '校验 · 运行 · 审批'],
    ['04', '高级项目', 'SRS 分期 · ZIP'],
    ['05', '运行观测', 'Token · 费用 · 续跑'],
    ['06', '平台能力', '主题 · 分桶 · Auth'],
  ].forEach((it, i) => {
    const x = 0.7 + (i % 3) * 4.15
    const y = 1.8 + Math.floor(i / 3) * 2.4
    panel(s, x, y, 3.95, 2.15)
    s.addText(it[0], {
      x: x + 0.25, y: y + 0.3, w: 3.4, h: 0.4,
      fontSize: 22, bold: true, color: T.mist, fontFace: FE,
    })
    s.addText(it[1], {
      x: x + 0.25, y: y + 0.85, w: 3.4, h: 0.4,
      fontSize: 16, bold: true, color: T.ink, fontFace: F,
    })
    s.addText(it[2], {
      x: x + 0.25, y: y + 1.4, w: 3.4, h: 0.4,
      fontSize: 12, color: T.mute, fontFace: F,
    })
  })
  footer(s)
}

partSlide(4, '核心功能', 'CORE FEATURES', '对话 · Studio · 工作流 · 高级项目')

const feats = [
  ['智能对话', 'Intelligent Chat', [
    '极速 / 专家 / Turbo / Pro 多模式',
    '写作 · PPT · 流程图 · 联网 · 语音',
    'DeepSeek 流式 + 技能轨统一入口',
  ]],
  ['工作台 Studio', 'Studio Delivery', [
    '需求 → 架构 → 代码 → 测试 → 部署',
    '大项目模式写入独立 workspaces',
    '完成后可下载 ZIP / 本地保存',
  ]],
  ['工作流编排', 'Workflow Engine', [
    'YAML Deliver 八节点画布',
    '校验 · 运行全流程 · 人工审批',
    '内部工单台作为演示用例',
  ]],
  ['高级项目', 'Advanced Projects', [
    '上传 SRS 自动规划里程碑',
    'P1 全链 / P2+ 增量短链',
    '只验收 · 一键导出 ZIP',
  ]],
  ['内置 Agent', 'Built-in Agents', [
    'Planner / Requirement / Coding',
    'Frontend / Testing / Debug',
    'Review / Ship 完整八角色',
  ]],
  ['插件工具', 'Tools & Plugins', [
    'Bocha 联网 · Pollinations 生图',
    '腾讯 ASR · Auth 会话',
    'Vite 代理统一接入',
  ]],
  ['运行观测', 'Observability', [
    'Run 状态 · SSE 流式日志',
    'Token / cost 费用统计',
    '失败原因与续跑入口',
  ]],
  ['平台能力', 'Platform', [
    '登录分桶 · 云雾浅昼主题',
    '管理台账号统计',
    '接口 / 测试 / 手册齐套',
  ]],
]

feats.forEach(([zh, en, lines], idx) => {
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, en, `${String(idx + 1).padStart(2, '0')}  ${zh}`)
  // 左侧色块
  s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 0.7, y: 1.85, w: 3.6, h: 4.7,
    fill: { color: T.wash },
    rectRadius: 0.1,
  })
  s.addText(String(idx + 1).padStart(2, '0'), {
    x: 0.95, y: 2.3, w: 3.1, h: 0.9,
    fontSize: 48, bold: true, color: T.mist, fontFace: FE,
  })
  s.addText(zh, {
    x: 0.95, y: 3.5, w: 3.1, h: 0.6,
    fontSize: 22, bold: true, color: T.ink, fontFace: F,
  })
  s.addText(en, {
    x: 0.95, y: 4.2, w: 3.1, h: 0.4,
    fontSize: 11, color: T.blue, fontFace: FE,
  })
  panel(s, 4.6, 1.85, 8.05, 4.7)
  s.addText('核心能力', {
    x: 5.0, y: 2.2, w: 7, h: 0.35,
    fontSize: 12, bold: true, color: T.blue, fontFace: F,
  })
  lines.forEach((ln, i) => {
    s.addShape(pptx.shapes.RECTANGLE, {
      x: 5.0, y: 2.9 + i * 1.0, w: 0.08, h: 0.55,
      fill: { color: T.blue },
    })
    s.addText(ln, {
      x: 5.3, y: 2.95 + i * 1.0, w: 6.9, h: 0.55,
      fontSize: 15, color: T.soft, fontFace: F, valign: 'middle',
    })
  })
  footer(s)
})

// ═══════════ 25 高级通栏 ═══════════
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Advanced', '高级项目与 PPT 生成')
  panel(s, 0.7, 1.85, 5.9, 4.7)
  s.addText('高级项目', {
    x: 1.05, y: 2.2, w: 5.2, h: 0.45,
    fontSize: 18, bold: true, color: T.ink, fontFace: F,
  })
  ;['多文档 SRS 入库与里程碑', '分期增量，避免重复全链', 'workspaces 独立工程与 ZIP'].forEach((t, i) => {
    s.addText(`0${i + 1}   ${t}`, {
      x: 1.05, y: 2.95 + i * 0.7, w: 5.2, h: 0.5,
      fontSize: 13, color: T.soft, fontFace: F,
    })
  })
  washBlock(s, 6.9, 1.85, 5.7, 4.7)
  s.addText('对话技能', {
    x: 7.25, y: 2.2, w: 5.2, h: 0.45,
    fontSize: 18, bold: true, color: T.ink, fontFace: F,
  })
  ;['PPT 生成与导出', '写作弹层 · Word 导出', '流程图多格式导出'].forEach((t, i) => {
    s.addText(`0${i + 1}   ${t}`, {
      x: 7.25, y: 2.95 + i * 0.7, w: 5.2, h: 0.5,
      fontSize: 13, color: T.soft, fontFace: F,
    })
  })
  footer(s)
}

partSlide(5, 'AI 核心能力', 'AI CAPABILITY', '模型分档、引擎机制与上下文管理')

// 27 多模型
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Models', '多模型统一适配')
  ;[
    ['DeepSeek V4 Pro', 'Coding / Frontend / Requirement', '高质量生成'],
    ['DeepSeek V4 Flash', 'Planner / Testing / Review / Ship', '编排收尾降本'],
    ['配置驱动', 'mawp.config.yaml · agents.models', '按角色分档'],
  ].forEach((m, i) => {
    const y = 1.85 + i * 1.55
    panel(s, 0.7, y, 7.5, 1.35)
    s.addText(m[0], { x: 1.05, y: y + 0.25, w: 6.8, h: 0.35, fontSize: 16, bold: true, color: T.ink, fontFace: F })
    s.addText(m[1], { x: 1.05, y: y + 0.7, w: 6.8, h: 0.35, fontSize: 12, color: T.mute, fontFace: F })
    washBlock(s, 8.5, y, 4.1, 1.35)
    s.addText(m[2], {
      x: 8.5, y: y + 0.45, w: 4.1, h: 0.45,
      fontSize: 14, bold: true, color: T.blueDeep, align: 'center', fontFace: F,
    })
  })
  footer(s)
}

// 28 引擎
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Engine', '智能体协议与工具调用')
  ;[
    ['YAML WorkflowEngine', '条件分支 · checkpoint · 循环上限'],
    ['SelfHeal', '测试/审查失败后有界回投 coding/debug'],
    ['真实冒烟', '拒绝空壳 200，业务字段验收'],
    ['工具代理', 'DeepSeek / Bocha / ASR / Image'],
  ].forEach((r, i) => {
    const x = 0.7 + (i % 2) * 6.2
    const y = 1.85 + Math.floor(i / 2) * 2.35
    panel(s, x, y, 5.95, 2.1)
    accentBar(s, x + 0.25, y + 0.4, 1.2)
    s.addText(r[0], { x: x + 0.5, y: y + 0.45, w: 5.1, h: 0.45, fontSize: 16, bold: true, color: T.ink, fontFace: F })
    s.addText(r[1], { x: x + 0.5, y: y + 1.1, w: 5.1, h: 0.55, fontSize: 13, color: T.soft, fontFace: F })
  })
  footer(s)
}

// 29 规划阶梯
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Planning', '任务规划与执行')
  ;[
    ['01', 'User Goal', '用户目标 / SRS'],
    ['02', 'Planner', '拆解 Deliver'],
    ['03', 'Requirement', '验收点沉淀'],
    ['04', 'Coding', '业务逻辑'],
    ['05', 'Frontend', '可打开页面'],
    ['06', 'Ship', '本地交付说明'],
  ].forEach((st, i) => {
    const y = 1.75 + i * 0.8
    const w = 8 + i * 0.55
    washBlock(s, 0.7, y, w, 0.68)
    s.addText(st[0], { x: 0.95, y: y + 0.15, w: 0.8, h: 0.4, fontSize: 14, bold: true, color: T.blueDeep, fontFace: FE })
    s.addText(st[1], { x: 1.9, y: y + 0.15, w: 3, h: 0.4, fontSize: 14, bold: true, color: T.ink, fontFace: F })
    s.addText(st[2], { x: 5.2, y: y + 0.15, w: 5, h: 0.4, fontSize: 12, color: T.mute, fontFace: F })
  })
  footer(s)
}

// 30 记忆
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Memory', '记忆与上下文')
  ;[
    ['短期', '当前会话 · SSE 流式上下文'],
    ['长期', 'chat-history 按 userId 分桶'],
    ['共享', 'Run 落盘 · workspaces 产物'],
  ].forEach((m, i) => {
    const y = 1.9 + i * 1.55
    s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
      x: 0.7, y, w: 12, h: 1.35,
      fill: { color: i === 1 ? T.mist : T.white },
      line: { color: i === 1 ? T.mist : T.line },
      rectRadius: 0.08,
    })
    s.addText(m[0], {
      x: 1.1, y: y + 0.4, w: 2.5, h: 0.5,
      fontSize: 20, bold: true, color: T.blueDeep, fontFace: F,
    })
    s.addText(m[1], {
      x: 4.0, y: y + 0.4, w: 8, h: 0.5,
      fontSize: 14, color: i === 1 ? '9BB0C0' : T.soft, fontFace: F,
    })
  })
  footer(s)
}

partSlide(6, '测试与部署', 'QA & DEPLOYMENT', '质量保障与本地部署')

// 32 流程
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Process', '开发流程')
  ;['需求分析', '架构设计', '编码实现', '测试验收', '文档交付'].forEach((n, i) => {
    const x = 0.55 + i * 2.5
    panel(s, x, 2.8, 2.3, 2.0)
    s.addText(String(i + 1).padStart(2, '0'), {
      x, y: 3.05, w: 2.3, h: 0.4,
      fontSize: 18, bold: true, color: T.blue, align: 'center', fontFace: FE,
    })
    s.addText(n, {
      x, y: 3.7, w: 2.3, h: 0.5,
      fontSize: 14, bold: true, color: T.ink, align: 'center', fontFace: F,
    })
  })
  footer(s)
}

// 33 测试
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'QA', '测试与质量保障')
  ;[
    ['E2E', '10%', '端到端演示路径'],
    ['集成', '30%', 'API / 工作流联调'],
    ['冒烟', '60%', 'Deliver 真实执行'],
  ].forEach((lv, i) => {
    const w = 5 + i * 2.2
    const x = (13.333 - w) / 2
    const y = 1.9 + i * 1.15
    s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
      x, y, w, h: 0.95,
      fill: { color: ['B8D4EA', '8FB8D6', '5A8FB5'][i] },
      rectRadius: 0.06,
    })
    s.addText(`${lv[0]}  ·  ${lv[1]}  ·  ${lv[2]}`, {
      x, y: y + 0.28, w, h: 0.4,
      fontSize: 14, bold: true, color: T.ink, align: 'center', fontFace: F,
    })
  })
  footer(s)
}

// 34 部署
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Deploy', '本地部署架构')
  ;[
    ['接入层', 'Vite :5173  ·  API 代理'],
    ['应用层', 'React UI  ·  FastAPI :8787'],
    ['数据层', '.mawp Run  ·  localStorage  ·  workspaces'],
  ].forEach((L, i) => {
    const y = 2.0 + i * 1.45
    if (i === 1) {
      s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
        x: 0.7, y, w: 12, h: 1.25,
        fill: { color: T.wash },
        rectRadius: 0.08,
      })
      s.addText(L[0], { x: 1.1, y: y + 0.2, w: 2.5, h: 0.35, fontSize: 14, bold: true, color: T.blue, fontFace: F })
      s.addText(L[1], { x: 1.1, y: y + 0.65, w: 10.5, h: 0.35, fontSize: 13, color: T.mute, fontFace: F })
    } else {
      panel(s, 0.7, y, 12, 1.25)
      s.addText(L[0], { x: 1.1, y: y + 0.2, w: 2.5, h: 0.35, fontSize: 14, bold: true, color: T.blueDeep, fontFace: F })
      s.addText(L[1], { x: 1.1, y: y + 0.65, w: 10.5, h: 0.35, fontSize: 13, color: T.soft, fontFace: F })
    }
  })
  footer(s)
}

// 35 性能安全
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Perf & Sec', '性能与安全')
  ;[
    ['流式响应', 'SSE，对话体验流畅'],
    ['模型分档', 'Flash 收尾降本'],
    ['用户分桶', '登录后数据隔离'],
    ['人工闸门', 'Review blocking'],
    ['真实冒烟', '拒绝空壳通过'],
    ['密钥代理', 'Key 不进前端'],
  ].forEach((m, i) => {
    const x = 0.7 + (i % 3) * 4.15
    const y = 1.9 + Math.floor(i / 3) * 2.3
    panel(s, x, y, 3.95, 2.0)
    s.addText(m[0], { x: x + 0.3, y: y + 0.5, w: 3.35, h: 0.45, fontSize: 16, bold: true, color: T.ink, fontFace: F })
    s.addText(m[1], { x: x + 0.3, y: y + 1.15, w: 3.35, h: 0.4, fontSize: 12, color: T.mute, fontFace: F })
  })
  footer(s)
}

// 36 创新点
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Innovation', '项目创新点')
  ;[
    ['01', '八 Agent 交付链', 'YAML 固化 Deliver，Testing↔Debug 可回环'],
    ['02', '可验收工程化', '真实冒烟 + 审查闸门，非假绿交付'],
    ['03', '云雾浅昼体验', '纸感 UI + 多技能对话统一入口'],
    ['04', '成本可观测', 'Run 级 Token / 费用，模型分档省钱'],
  ].forEach((v, i) => {
    const y = 1.8 + i * 1.2
    panel(s, 0.7, y, 12, 1.05)
    s.addText(v[0], {
      x: 1.0, y: y + 0.2, w: 1.3, h: 0.65,
      fontSize: 28, bold: true, color: T.mist, fontFace: FE,
    })
    s.addText(v[1], {
      x: 2.5, y: y + 0.15, w: 4, h: 0.35,
      fontSize: 16, bold: true, color: T.ink, fontFace: F,
    })
    s.addText(v[2], {
      x: 2.5, y: y + 0.55, w: 9.5, h: 0.35,
      fontSize: 12, color: T.mute, fontFace: F,
    })
  })
  footer(s)
}

partSlide(7, '总结与展望', 'SUMMARY & OUTLOOK', '成果、规划与致谢')

// 38 场景
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Scenarios', '应用场景')
  ;[
    ['实训交付', '课程项目 · 答辩演示 · 全链验收'],
    ['内部工单', 'IT 报修 MVP · 本地可打开'],
    ['分期大项目', 'SRS 里程碑 · workspaces ZIP'],
    ['技能生产力', '写作 / PPT / 流程图 / 联网'],
  ].forEach((v, i) => {
    const x = 0.7 + (i % 2) * 6.2
    const y = 1.85 + Math.floor(i / 2) * 2.35
    if (i === 0) {
      s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
        x, y, w: 5.95, h: 2.1,
        fill: { color: T.wash },
        rectRadius: 0.08,
      })
      s.addText(v[0], { x: x + 0.35, y: y + 0.45, w: 5.2, h: 0.45, fontSize: 18, bold: true, color: T.ink, fontFace: F })
      s.addText(v[1], { x: x + 0.35, y: y + 1.1, w: 5.2, h: 0.45, fontSize: 13, color: T.mute, fontFace: F })
    } else {
      panel(s, x, y, 5.95, 2.1)
      s.addText(v[0], { x: x + 0.35, y: y + 0.45, w: 5.2, h: 0.45, fontSize: 18, bold: true, color: T.ink, fontFace: F })
      s.addText(v[1], { x: x + 0.35, y: y + 1.1, w: 5.2, h: 0.45, fontSize: 13, color: T.mute, fontFace: F })
    }
  })
  footer(s)
}

// 39 roadmap
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Roadmap', '未来规划')
  s.addShape(pptx.shapes.RECTANGLE, {
    x: 1.0, y: 3.5, w: 11.3, h: 0.04,
    fill: { color: T.mist },
  })
  ;[
    ['V1.0', 'Q2', '八 Agent · Studio · 工作流'],
    ['V1.5', 'Q3', '技能与工作流打通'],
    ['V2.0', 'Q4', '云端会话 · 审计'],
    ['V3.0', '2027', '多租户 · 插件市场'],
  ].forEach((v, i) => {
    const x = 1.0 + i * 3.0
    s.addShape(pptx.shapes.OVAL, {
      x: x + 0.95, y: 3.35, w: 0.35, h: 0.35,
      fill: { color: T.blueDeep },
    })
    panel(s, x, 4.0, 2.7, 2.0)
    s.addText(v[0], { x, y: 4.25, w: 2.7, h: 0.4, fontSize: 18, bold: true, color: T.blueDeep, align: 'center', fontFace: FE })
    s.addText(v[1], { x, y: 4.7, w: 2.7, h: 0.3, fontSize: 11, color: T.mute, align: 'center', fontFace: F })
    s.addText(v[2], { x: x + 0.15, y: 5.15, w: 2.4, h: 0.55, fontSize: 11, color: T.soft, align: 'center', fontFace: F })
  })
  footer(s)
}

// 40 总结三栏
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  pageHead(s, 'Summary', '项目总结')
  ;[
    ['做了什么', ['智流 UI + MAWP 打通', '八 Agent 主链可跑', '工单台等演示用例']],
    ['解决了什么', ['交付不可控 → 可验收', '过程黑盒 → 可观测', '成本盲区 → 可分档']],
    ['收获了什么', ['多 Agent 工程实践', '文档与测试体系', '可答辩产品']],
  ].forEach((c, i) => {
    const x = 0.7 + i * 4.15
    if (i === 1) {
      s.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
        x, y: 1.85, w: 3.95, h: 4.7,
        fill: { color: T.wash },
        rectRadius: 0.1,
      })
      s.addText(c[0], { x: x + 0.25, y: 2.2, w: 3.45, h: 0.45, fontSize: 16, bold: true, color: T.ink, fontFace: F })
      c[1].forEach((ln, j) => {
        s.addText(`·  ${ln}`, { x: x + 0.25, y: 3.0 + j * 0.7, w: 3.45, h: 0.55, fontSize: 13, color: T.mute, fontFace: F })
      })
    } else {
      panel(s, x, 1.85, 3.95, 4.7)
      s.addText(c[0], { x: x + 0.25, y: 2.2, w: 3.45, h: 0.45, fontSize: 16, bold: true, color: T.ink, fontFace: F })
      c[1].forEach((ln, j) => {
        s.addText(`·  ${ln}`, { x: x + 0.25, y: 3.0 + j * 0.7, w: 3.45, h: 0.55, fontSize: 13, color: T.soft, fontFace: F })
      })
    }
  })
  footer(s)
}

// 41 尾页
{
  const s = pptx.addSlide()
  tick()
  paperBg(s)
  s.addText('感谢聆听', {
    x: 0.9, y: 2.5, w: 11.5, h: 0.9,
    fontSize: 48, bold: true, color: T.ink, fontFace: F,
  })
  s.addText('THANK YOU FOR YOUR ATTENTION', {
    x: 0.9, y: 3.5, w: 11.5, h: 0.4,
    fontSize: 13, color: T.blue, fontFace: FE, charSpacing: 3,
  })
  s.addShape(pptx.shapes.RECTANGLE, {
    x: 0.9, y: 4.2, w: 1.8, h: 0.025,
    fill: { color: T.accent },
  })
  s.addText('云计算 2508A 第四组  ·  智流 AgentFlow', {
    x: 0.9, y: 4.55, w: 11, h: 0.4,
    fontSize: 14, color: T.mute, fontFace: F,
  })
  s.addText('欢迎各位老师批评指正', {
    x: 0.9, y: 5.15, w: 11, h: 0.35,
    fontSize: 12, color: T.mute, fontFace: F,
  })
  footer(s)
}

if (N !== TOTAL) {
  console.error('slide count', N, 'expected', TOTAL)
  process.exit(1)
}

fs.mkdirSync(path.dirname(OUT), { recursive: true })
await pptx.writeFile({ fileName: OUT })
if (DESKTOP) {
  try {
    fs.copyFileSync(OUT, DESKTOP)
  } catch {
    const alt = path.join(process.env.USERPROFILE, 'Desktop', '智流AgentFlow-答辩-杂志版.pptx')
    fs.copyFileSync(OUT, alt)
    console.log('Desktop locked, wrote', alt)
  }
}
console.log('OK magazine', N, '->', OUT)
if (DESKTOP) console.log('Desktop', DESKTOP)
