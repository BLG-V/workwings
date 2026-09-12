/**
 * 按「02-需求规格说明书-大纲.docx」同款排版生成 04/05/06 三份 Word
 * - 封面居中 + 分页
 * - Heading1 / Heading2
 * - ListBullet 列表
 * - TableGrid 表格
 * - 复用大纲文档的 styles / numbering / theme
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import JSZip from 'jszip'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')
const OUT_DIR = path.join(ROOT, 'docs', 'course-submit')
const DESKTOP = process.env.USERPROFILE
  ? path.join(process.env.USERPROFILE, 'Desktop')
  : ''
const TEMPLATE =
  'd:/wx/xwechat_files/wxid_xfn1hprdke1922_887b/msg/file/2026-08/02-需求规格说明书-大纲.docx'

const FONT = '宋体'
const DATE = '2026-08-22'

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function rPr({ bold = false, size = 24, highlight = null } = {}) {
  const b = bold ? '<w:b/>' : '<w:b w:val="0"/>'
  const hl = highlight ? `<w:highlight w:val="${highlight}"/>` : ''
  return `<w:rPr><w:rFonts w:ascii="${FONT}" w:hAnsi="${FONT}" w:eastAsia="${FONT}"/>${b}<w:sz w:val="${size}"/><w:szCs w:val="${size}"/>${hl}</w:rPr>`
}

function run(text, opts = {}) {
  return `<w:r>${rPr(opts)}<w:t xml:space="preserve">${esc(text)}</w:t></w:r>`
}

function pBody(text, opts = {}) {
  return `<w:p><w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/></w:pPr>${run(text, { size: opts.size || 24, bold: opts.bold, highlight: opts.highlight })}</w:p>`
}

function pCenter(text, { size = 24, bold = false, after = 120 } = {}) {
  return `<w:p><w:pPr><w:spacing w:after="${after}" w:line="360" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>${run(text, { size, bold })}</w:p>`
}

function h1(text) {
  return `<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>${run(text, { size: 32, bold: true })}</w:p>`
}

function h2(text) {
  return `<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>${run(text, { size: 28, bold: true })}</w:p>`
}

function h3(text) {
  return `<w:p><w:pPr><w:pStyle w:val="Heading3"/></w:pPr>${run(text, { size: 24, bold: true })}</w:p>`
}

function bullet(text) {
  return `<w:p><w:pPr><w:pStyle w:val="ListBullet"/><w:ind w:left="425"/><w:spacing w:after="60" w:line="360" w:lineRule="auto"/></w:pPr>${run(text, { size: 24 })}</w:p>`
}

function note(kind, text) {
  const label =
    kind === 'shot'
      ? '【截图标注】'
      : kind === 'fill'
        ? '【填写标注】'
        : kind === 'warn'
          ? '【注意标注】'
          : '【标注】'
  return pBody(`${label} ${text}`, { size: 22, bold: true, highlight: 'yellow' })
}

function empty() {
  return '<w:p/>'
}

function pageBreak() {
  return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
}

function table(headers, rows) {
  const cols = headers.length
  const width = Math.floor(9400 / cols)
  const grid = Array.from({ length: cols }, () => `<w:gridCol w:w="${width}"/>`).join(
    '',
  )
  const cell = (text, header = false) =>
    `<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="${width}"/></w:tcPr><w:p>${run(text, {
      size: 20,
      bold: header,
    })}</w:p></w:tc>`
  const headerRow = `<w:tr>${headers.map((h) => cell(h, true)).join('')}</w:tr>`
  const body = rows
    .map((row) => `<w:tr>${row.map((c) => cell(c ?? '')).join('')}</w:tr>`)
    .join('')
  return `<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:type="auto" w:w="0"/><w:jc w:val="center"/><w:tblLook w:firstColumn="1" w:firstRow="1" w:lastColumn="0" w:lastRow="0" w:noHBand="0" w:noVBand="1" w:val="04A0"/></w:tblPr><w:tblGrid>${grid}</w:tblGrid>${headerRow}${body}</w:tbl>${empty()}`
}

function cover({ title, subtitle, docType }) {
  return [
    empty(),
    empty(),
    empty(),
    empty(),
    pCenter(title, { size: 44, bold: true, after: 360 }),
    pCenter(subtitle, { size: 32, bold: true, after: 720 }),
    pCenter('项目名称：智流 AgentFlow / MAWP 多 Agent 工作流平台', {
      size: 28,
      after: 120,
    }),
    pCenter(`文档类型：${docType}`, { size: 24, after: 120 }),
    pCenter('文档版本：v2.0（全功能）', { size: 24, after: 120 }),
    pCenter(`编写日期：${DATE}`, { size: 24, after: 120 }),
    pCenter('适用范围：实训交付 / 设计开发 / 测试验收 / 答辩', {
      size: 24,
      after: 120,
    }),
    note('fill', '请补全：课程名称 / 小组 / 学号姓名 / Gitee 仓库地址'),
    pageBreak(),
  ].join('')
}

function docControl(revisionNote, relatedRows) {
  return [
    h1('文档控制'),
    pBody('修订记录'),
    table(
      ['版本', '日期', '修订人', '说明'],
      [
        ['v1.0', '2026-08-21', '—', '初稿'],
        ['v2.0', DATE, '—', revisionNote],
      ],
    ),
    pBody('关联文档'),
    table(['文档', '说明'], relatedRows),
    note('fill', '修订人栏填写实际编写同学姓名'),
  ].join('')
}

function sectPr() {
  return `<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="720" w:footer="720" w:gutter="0"/><w:cols w:space="720"/><w:docGrid w:linePitch="360"/></w:sectPr>`
}

async function loadTemplateParts() {
  const z = await JSZip.loadAsync(fs.readFileSync(TEMPLATE))
  const pick = async (name) => {
    const f = z.file(name)
    return f ? await f.async('nodebuffer') : null
  }
  return {
    styles: await pick('word/styles.xml'),
    stylesWithEffects: await pick('word/stylesWithEffects.xml'),
    numbering: await pick('word/numbering.xml'),
    settings: await pick('word/settings.xml'),
    webSettings: await pick('word/webSettings.xml'),
    fontTable: await pick('word/fontTable.xml'),
    theme: await pick('word/theme/theme1.xml'),
  }
}

async function writeDocx(filename, bodyXml, template) {
  const documentXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    ${bodyXml}
    ${sectPr()}
  </w:body>
</w:document>`

  const zip = new JSZip()
  zip.file(
    '[Content_Types].xml',
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/stylesWithEffects.xml" ContentType="application/vnd.ms-word.stylesWithEffects+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/webSettings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml"/>
  <Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>`,
  )
  zip.folder('_rels').file(
    '.rels',
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>`,
  )
  zip.folder('docProps').file(
    'core.xml',
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
  xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>${esc(filename)}</dc:title>
  <dc:creator>智流 AgentFlow</dc:creator>
  <cp:lastModifiedBy>智流 AgentFlow</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">${DATE}T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">${DATE}T00:00:00Z</dcterms:modified>
</cp:coreProperties>`,
  )
  zip.folder('docProps').file(
    'app.xml',
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>AgentFlow Course Docs</Application>
</Properties>`,
  )

  const word = zip.folder('word')
  word.file('document.xml', documentXml)
  word.file('styles.xml', template.styles)
  if (template.stylesWithEffects)
    word.file('stylesWithEffects.xml', template.stylesWithEffects)
  if (template.numbering) word.file('numbering.xml', template.numbering)
  if (template.settings) word.file('settings.xml', template.settings)
  if (template.webSettings) word.file('webSettings.xml', template.webSettings)
  if (template.fontTable) word.file('fontTable.xml', template.fontTable)
  word.folder('theme').file('theme1.xml', template.theme)
  word.folder('_rels').file(
    'document.xml.rels',
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/webSettings" Target="webSettings.xml"/>
  <Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>
  <Relationship Id="rId6" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>`,
  )

  const buf = await zip.generateAsync({ type: 'nodebuffer' })
  fs.mkdirSync(OUT_DIR, { recursive: true })
  const out = path.join(OUT_DIR, filename)
  fs.writeFileSync(out, buf)
  if (DESKTOP && fs.existsSync(DESKTOP)) {
    fs.writeFileSync(path.join(DESKTOP, filename), buf)
  }
  return out
}

/* ===================== 04 接口设计 ===================== */
function apiBody() {
  return [
    cover({
      title: '接口设计文档',
      subtitle: '（API 规格 · 全功能 · 可对照实现）',
      docType: '接口设计文档',
    }),
    docControl('按当前仓库全量功能重排：Platform / Auth / ASR / Image / 代理', [
      ['README.md', '产品简介与快速启动'],
      ['src/lib/mawp-api.ts', '前端 Platform API 封装'],
      ['vite.config.ts', 'DeepSeek / Bocha / Pollinations / mawp 代理'],
      ['backend/src/mawp/api/platform.py', 'Platform 路由'],
      ['backend/src/mawp/auth/routes.py', '认证路由'],
      ['02-需求规格说明书-大纲.docx', '排版样式参照'],
    ]),

    h1('1 引言'),
    h2('1.1 编写目的'),
    bullet('约定智流前后端 HTTP / WebSocket / 开发代理的路径、报文与错误码'),
    bullet('作为前后端联调、测试用例与答辩演示的统一接口依据'),
    bullet('接口名与当前代码仓库保持一致，便于对照实现'),
    h2('1.2 范围'),
    pBody('范围内：'),
    bullet('Vite 代理：/api/mawp、/api/deepseek、/api/bocha、/api/pollinations'),
    bullet('MAWP Platform：健康检查、工作流 validate/run/resume、Studio Deliver、Advanced、Run'),
    bullet('Auth / ASR / Image 后端路由'),
    pBody('范围外：'),
    bullet('Agent 内部提示词与工具实现细节（见设计/代码）'),
    bullet('第三方上游 OpenAPI 全文（仅列本系统使用的路径）'),
    note('shot', '可贴架构图：浏览器 → Vite → FastAPI:8787 / 外网 API'),

    h1('2 总体约定'),
    h2('2.1 Base URL'),
    table(
      ['环境', '地址'],
      [
        ['前端开发', 'http://127.0.0.1:<Vite端口>'],
        ['内核直连', 'http://127.0.0.1:8787'],
        ['浏览器访问内核', '前缀 /api/mawp → 后端 /api'],
      ],
    ),
    h2('2.2 代理映射'),
    table(
      ['前缀', '目标', '说明'],
      [
        ['/api/mawp/*', 'http://127.0.0.1:8787/api/*', 'HTTP + WebSocket'],
        ['/api/deepseek/*', 'https://api.deepseek.com', '注入 DEEPSEEK_API_KEY，SSE'],
        ['/api/bocha/*', 'https://api.bochaai.com', '联网搜索 BOCHA_API_KEY'],
        ['/api/pollinations/*', 'https://gen.pollinations.ai', '文生图，可选 Key'],
      ],
    ),
    h2('2.3 通用错误码'),
    table(
      ['HTTP', '含义', '典型 detail'],
      [
        ['200', '成功', '业务 JSON'],
        ['400', '参数错误', 'goal 为空 / YAML 非法'],
        ['401/403', '鉴权失败', 'Token 无效 / 无权限'],
        ['404', '资源不存在', 'run / 文件不存在'],
        ['500', '服务端失败', '执行失败 / 上游异常'],
      ],
    ),
    note('fill', '补充本组实际 Vite 端口号'),

    h1('3 健康检查与平台信息'),
    h2('3.1 GET /api/mawp/health'),
    pBody('用途：探测内核是否在线、LLM 与按 Agent 模型配置。'),
    pBody('响应字段：status、service、workspace、llm、agent_models。'),
    note('shot', '贴 curl 或浏览器返回 JSON 截图'),
    h2('3.2 GET /api/mawp/platform/info'),
    pBody('平台信息摘要。'),
    h2('3.3 GET|POST /api/mawp/platform/models'),
    pBody('查询或更新八 Agent 分模型（deepseek-v4-flash / deepseek-v4-pro 等）。'),

    h1('4 工作流接口（校验 / 运行 / 审批）'),
    h2('4.1 POST /api/mawp/platform/workflows/validate'),
    pBody('请求：path 或 yaml_text。响应：ok、workflow_id、errors[]。'),
    note('shot', '编排页「校验内核」通过截图'),
    h2('4.2 POST /api/mawp/platform/workflows/run'),
    pBody('请求：path、params（goal / pass_on_attempt / review_status 等）、async_mode。'),
    pBody('响应：run（run_id、status、current_node_id、params…）。'),
    h2('4.3 POST /api/mawp/platform/runs/{run_id}/resume'),
    pBody('action：approve | reject | input。用于 Review blocking 人工确认后续跑。'),
    h2('4.4 POST /api/mawp/platform/runs/{run_id}/retry'),
    pBody('失败 Run 重试。'),
    h2('4.5 GET /api/mawp/platform/runs · GET .../runs/{id}'),
    pBody('列表与详情（events、observe：token / cost_cny / by_agent）。'),
    note('shot', '运行中 / DONE / WAITING_USER 各一张'),

    h1('5 Studio Deliver 与工作区'),
    h2('5.1 POST /api/mawp/platform/studio/deliver'),
    pBody(
      '请求要点：goal、async_mode、review_status、pass_on_attempt、project_mode、project_title、create_workspace。',
    ),
    bullet('project_mode=false：常写入 demo-code-agent/frontend'),
    bullet('project_mode=true：workspaces/studio-*/apps/{api,web}'),
    h2('5.2 阶段与流'),
    bullet('GET .../studio/runs/{id}/stages'),
    bullet('GET .../studio/runs/{id}/stream（SSE）'),
    h2('5.3 文件与版本'),
    bullet('GET tree / file / zip?project_root='),
    bullet('versions 创建/diff/restore；diff / diff-compare；POST save'),
    note('warn', '未开大项目模式时无一键 ZIP，需手动打包 frontend'),

    h1('6 高级项目 Advanced'),
    table(
      ['方法', '路径', '说明'],
      [
        ['GET/POST', '/api/mawp/platform/advanced/projects', '列表 / 创建'],
        ['POST', '.../projects/{id}/generate', '生成当前期'],
        ['POST', '.../generate-remaining', '生成剩余里程碑'],
        ['GET', '.../export.zip', '导出 ZIP'],
        ['GET', '.../tree · /file', '工作区浏览'],
      ],
    ),
    pBody('工作区：workspaces/ap-*/。P1 全链；P2+ 增量；支持只验收。'),
    note('shot', '高级项目导出 ZIP 截图'),

    h1('7 认证 Auth'),
    table(
      ['方法', '路径', '说明'],
      [
        ['GET', '/api/mawp/auth/captcha', '图形验证码'],
        ['POST', '/api/mawp/auth/send-code', '发短信/邮箱码'],
        ['POST', '/api/mawp/auth/login-password', '密码+验证码登录'],
        ['POST', '/api/mawp/auth/verify', 'OTP 登录/注册'],
        ['GET/PATCH', '/api/mawp/auth/me', '当前用户（Bearer）'],
        ['GET', '/api/mawp/auth/avatars/{file}', '头像'],
        ['GET', '/api/mawp/auth/users', '管理员用户列表'],
      ],
    ),
    pBody('前端会话：mawp-auth-token、mawp-auth-user；业务数据按 userId 分桶。'),
    note('fill', '演示账号只写用户名，勿写密码'),

    h1('8 语音 ASR 与图像 Image'),
    bullet('GET /api/mawp/asr/status'),
    bullet('WS /api/mawp/asr/realtime（腾讯云，需 TENCENT_*）'),
    bullet('GET /api/mawp/image/status'),
    bullet('POST /api/mawp/image/generate（Pollinations Flux）'),
    note('shot', '可选：语音条 / 生图结果'),

    h1('9 上游代理（对话技能）'),
    h2('9.1 DeepSeek /api/deepseek/*'),
    bullet('Chat Completions 流式：对话、写作、需求分析、流程图 JSON 等'),
    bullet('模型：deepseek-v4-flash / deepseek-v4-pro'),
    h2('9.2 Bocha /api/bocha/v1/web-search'),
    pBody('联网搜索。'),
    h2('9.3 Pollinations /api/pollinations/*'),
    pBody('文生图通道。'),
    note('shot', 'Network 各贴一条成功请求'),

    h1('10 环境变量'),
    table(
      ['位置', '变量', '用途'],
      [
        ['根 .env', 'DEEPSEEK_API_KEY', '对话+代理+内核'],
        ['根 .env', 'BOCHA_API_KEY', '联网搜索'],
        ['根/后端', 'POLLINATIONS_*', '文生图（可选）'],
        ['backend/.env', 'AUTH_* / SMTP_* / ALIYUN_*', '验证码登录'],
        ['backend/.env', 'TENCENT_*', '实时 ASR'],
      ],
    ),
    note('warn', '真实 Key 勿提交 Git'),

    h1('11 接口速查总表'),
    bullet('健康：GET /api/mawp/health'),
    bullet('工作流：validate / run / resume / retry / runs'),
    bullet('Studio：deliver / stages / stream / project/*'),
    bullet('Advanced：projects + generate + export.zip'),
    bullet('Auth / ASR / Image 见第 7～8 章'),
    bullet('代理：/api/deepseek/* · /api/bocha/* · /api/pollinations/*'),
    note('fill', '可再附 Postman/Apifox 集合链接'),
  ].join('')
}

/* ===================== 05 测试 ===================== */
function testBody() {
  return [
    cover({
      title: '测试文档',
      subtitle: '（测试计划 · 用例 · 结果 · 可附截图）',
      docType: '测试文档',
    }),
    docControl('按全功能补齐技能/Studio/高级项目/隔离/主题用例', [
      ['04-接口设计文档.docx', '接口依据'],
      ['06-用户操作手册.docx', '操作步骤依据'],
      ['apps/demo-code-agent/workflows/deliver.yaml', 'Deliver 链'],
      ['02-需求规格说明书-大纲.docx', '排版样式参照'],
    ]),

    h1('1 引言'),
    h2('1.1 编写目的'),
    bullet('给出可执行的测试计划与用例，支撑冒烟、功能、联调与答辩验收'),
    bullet('覆盖当前仓库已实现的全部主功能（含对话技能与多用户隔离）'),
    h2('1.2 测试环境（填写）'),
    table(
      ['项', '内容'],
      [
        ['操作系统', '【填写】'],
        ['Node / Python', '【填写】'],
        ['浏览器', '【填写】'],
        ['测试人员', '【填写】'],
        ['测试日期', '【填写】'],
      ],
    ),
    note('shot', '建议每个通过用例附编号截图'),

    h1('2 测试计划'),
    h2('2.1 范围'),
    bullet('冒烟：启动、登录、健康检查、默认主题'),
    bullet('权限：RequireAuth、A/B 用户数据隔离、管理台'),
    bullet('对话技能：模式切换、写作/PPT/流程图/联网/图像/语音/附件'),
    bullet('Studio / 工作流八 Agent / 高级项目 / 运行记录 / 设置'),
    bullet('前后端联调与代理'),
    h2('2.2 准备步骤'),
    bullet('npm install；npm run backend:install'),
    bullet('配置 DEEPSEEK_API_KEY；可选 BOCHA / TENCENT / POLLINATIONS'),
    bullet('终端A：npm run backend:serve；终端B：npm run dev'),
    note('shot', '双终端启动 + 内核在线'),

    h1('3 冒烟测试'),
    table(
      ['编号', '步骤', '预期', '结果'],
      [
        ['TC-S01', '打开登录页', '无白屏', '【填写】'],
        ['TC-S02', '登录进入首页', '进入智能对话', '【填写】'],
        ['TC-S03', 'GET /api/mawp/health', 'status=ok', '【填写】'],
        ['TC-S04', '查看默认主题', '云雾浅昼或设置标注默认', '【填写】'],
        ['TC-S05', '侧栏模块齐全', '工作台/高级/项目/Agent/运行/设置可见', '【填写】'],
      ],
    ),
    note('shot', '首页全貌 + health JSON'),

    h1('4 登录权限与数据隔离'),
    table(
      ['编号', '步骤', '预期', '结果'],
      [
        ['TC-A01', '未登录访问 /projects', '跳转 /login', '【填写】'],
        ['TC-A02', 'A 对话后换 B 登录', 'B 无 A 历史', '【填写】'],
        ['TC-A03', 'A 再登录', 'A 历史仍在', '【填写】'],
        ['TC-A04', '普通用户访问 /admin', '不可进入', '【填写】'],
        ['TC-A05', '管理员访问 /admin', '可见账号列表', '【填写】'],
      ],
    ),
    note('shot', 'A/B 侧栏对比'),
    note('fill', '测试账号用户名 A=____ B=____（勿写密码）'),

    h1('5 智能对话与技能'),
    table(
      ['编号', '功能', '预期', '结果'],
      [
        ['TC-C01', '极速/专家/Turbo/Pro', '可切换', '【填写】'],
        ['TC-C02', '流式+思考过程', '专家/Pro 可见思考', '【填写】'],
        ['TC-C03', '帮我写作→导出 docx', '成稿可下载', '【填写】'],
        ['TC-C04', '需求分析', '输出 PRD Markdown', '【填写】'],
        ['TC-C05', 'PPT 生成', '下载 pptx', '【填写】'],
        ['TC-C06', '流程图导出', '至少一种格式成功', '【填写】'],
        ['TC-C07', '联网搜索', '开/关有效（需 Key）', '【填写】'],
        ['TC-C08', '图像生成', '出图或明确失败原因', '【填写】'],
        ['TC-C09', '深入研究/AI播客', '有输出', '【填写】'],
        ['TC-C10', '语音输入', '成功或标注未配置跳过', '【填写】'],
        ['TC-C11', '上传附件', '可发送', '【填写】'],
        ['TC-C12', '暗色主题菜单文字', '可读（非深灰吞字）', '【填写】'],
      ],
    ),
    note('shot', '写作/流程图/PPT/联网/图像至少各一张'),
    note('warn', '未配置 Key 的用例记「跳过」并写原因'),

    h1('6 Studio 与工作流 Agent 链'),
    h2('6.1 Studio'),
    table(
      ['编号', '步骤', '预期', '结果'],
      [
        ['TC-ST01', '五阶段切换', '需求/架构/代码/测试/部署', '【填写】'],
        ['TC-ST02', '需求分析生成', '触发完整 Deliver', '【填写】'],
        ['TC-ST03', '不勾大项目跑通', '产物可打开', '【填写】'],
        ['TC-ST04', '勾大项目模式', 'workspaces/studio-*', '【填写】'],
        ['TC-ST05', '导出 ZIP/保存本地', '可下载或写入', '【填写】'],
      ],
    ),
    h2('6.2 工作流编排'),
    table(
      ['编号', '步骤', '预期', '结果'],
      [
        ['TC-W01', '打开编排画布', '八节点只读可见', '【填写】'],
        ['TC-W02', '校验内核', '通过', '【填写】'],
        ['TC-W03', '填写目标后运行全流程', '开始执行（非只写目标）', '【填写】'],
        ['TC-W04', '跑完 Deliver', 'DONE，八 Agent 有产出', '【填写】'],
        ['TC-W05', '工单台产物验收', '增删改状态+刷新不丢', '【填写】'],
        ['TC-W06', 'blocking→通过', '可续跑到 ship', '【填写】'],
      ],
    ),
    note('warn', '写入目标 ≠ 自动运行，须点「运行全流程」'),
    note('shot', '运行日志 + 工单台操作 + observe'),

    h1('7 高级项目与其它页面'),
    table(
      ['编号', '步骤', '预期', '结果'],
      [
        ['TC-AD01', '上传 SRS 建项目', 'ap-* 创建成功', '【填写】'],
        ['TC-AD02', '生成当前期', '有产物', '【填写】'],
        ['TC-AD03', '只验收', '不重生成', '【填写】'],
        ['TC-AD04', '生成剩余', '多期推进', '【填写】'],
        ['TC-AD05', '导出 ZIP', '可下载', '【填写】'],
        ['TC-R01', '运行记录页', '可见 Run 详情/审批', '【填写】'],
        ['TC-P01', '项目管理', '可建项进工作流', '【填写】'],
        ['TC-SE01', '设置/主题切换', '六套主题可用', '【填写】'],
      ],
    ),
    note('shot', '高级项目 ZIP + 运行记录'),

    h1('8 前后端联调'),
    table(
      ['编号', '步骤', '预期', '结果'],
      [
        ['TC-I01', '停后端', '内核离线提示', '【填写】'],
        ['TC-I02', '恢复后端', '内核在线', '【填写】'],
        ['TC-I03', '无 DeepSeek Key', '明确失败提示', '【填写】'],
        ['TC-I04', '查看 Network', '见 /api/mawp 与 /api/deepseek', '【填写】'],
        ['TC-I05', 'ASR/生图 status', '可探测配置状态', '【填写】'],
      ],
    ),
    note('shot', '离线对比 + Network'),

    h1('9 结果汇总与缺陷'),
    pBody('请将第 3～8 章表格「结果」列汇总为通过率，并列出缺陷。'),
    table(
      ['缺陷编号', '现象', '复现', '状态'],
      [
        ['BUG-01', '【填写】', '【填写】', '【填写】'],
        ['BUG-02', '【填写】', '【填写】', '【填写】'],
      ],
    ),
    bullet('风险：大项目模式 token 成本高；部分技能依赖第三方 Key'),
    note('fill', '统计：用例总数____ 通过____ 失败____ 跳过____'),
  ].join('')
}

/* ===================== 06 手册 ===================== */
function manualBody() {
  return [
    cover({
      title: '用户操作手册',
      subtitle: '（给老师演示用 · 从安装到导出）',
      docType: '用户操作手册',
    }),
    docControl('按全功能演示路径重写：对话技能 + Studio + 工作流 + 高级项目 + 导出', [
      ['README.md', '快速启动'],
      ['04-接口设计文档.docx', '接口说明'],
      ['05-测试文档.docx', '验收对照'],
      ['02-需求规格说明书-大纲.docx', '排版样式参照'],
    ]),

    h1('1 引言'),
    h2('1.1 编写目的'),
    bullet('指导完成安装启动、登录、对话/Studio、跑工作流、看运行记录、导出产物'),
    bullet('作为课程答辩演示脚本（建议 8～12 分钟）'),
    h2('1.2 读者对象'),
    bullet('课程指导教师、评审老师、项目组成员'),
    note('fill', '封面已含项目信息；此处可再写演示人姓名'),

    h1('2 安装与启动'),
    h2('2.1 环境依赖'),
    bullet('Node.js 18+、Python 3.11+、Git'),
    bullet('必填：DEEPSEEK_API_KEY'),
    bullet('可选：BOCHA、腾讯云 ASR、Pollinations、邮箱/短信验证码'),
    h2('2.2 安装'),
    pBody('git clone <仓库> → cd agentflow → npm install → npm run backend:install'),
    pBody('在根目录或 backend/.env 填写 DEEPSEEK_API_KEY。'),
    h2('2.3 启动（两个终端）'),
    table(
      ['终端', '命令', '地址'],
      [
        ['A', 'npm run backend:serve', 'http://127.0.0.1:8787'],
        ['B', 'npm run dev', 'Vite 提示的本地地址'],
      ],
    ),
    note('shot', '双终端日志 + 浏览器首页'),
    note('warn', '只开前端会显示内核离线，工作流无法执行'),

    h1('3 登录与多用户说明'),
    bullet('打开站点 → 登录（密码+图形码，或手机/邮箱验证码）'),
    bullet('登录后进入「智能对话」；历史会话按账号隔离'),
    bullet('可演示：账号 A 对话 → 退出 → 账号 B 看不到 A 的记录'),
    bullet('管理员可进入「管理台」'),
    note('shot', '登录页 → 首页；可选 A/B 对比'),
    note('fill', '演示账号用户名：____'),

    h1('4 智能对话（技能导览）'),
    h2('4.1 回复模式'),
    bullet('极速 / 专家 / 工作任务 Turbo / 工作任务 Pro（深度思考）'),
    h2('4.2 技能与输入'),
    table(
      ['能力', '入口', '说明'],
      [
        ['联网搜索', '技能轨开关', '需 BOCHA_API_KEY'],
        ['需求分析', '技能轨', 'DeepSeek 输出 PRD'],
        ['帮我写作', '技能轨', '成稿弹层，可导出 Word'],
        ['PPT 生成', '技能轨', '下载 pptx'],
        ['流程图', '技能轨', '可编辑，多格式导出'],
        ['图像生成', '更多', 'Pollinations / 后端 image'],
        ['深入研究', '更多', '资料检索辅助'],
        ['AI 播客', '更多', '口播稿 + 朗读'],
        ['语音输入', '麦克风/空格', '需腾讯云 ASR'],
        ['上传', '加号', '文件/图片'],
      ],
    ),
    note('shot', '现场演示 2～3 个技能并截图'),
    note('warn', '未配置的能力可跳过并口头说明'),

    h1('5 工作台 Studio'),
    bullet('侧栏进入「工作台」'),
    bullet('五阶段：需求分析 → 架构 → 代码 → 测试 → 部署'),
    bullet('在需求分析粘贴目标；首次建议不勾「大项目工程模式」'),
    bullet('点生成等待 Deliver；其它阶段查看同一次 Run 产物'),
    bullet('勾选大项目：产物写入 workspaces/studio-*，完成后可下载 ZIP'),
    note('shot', 'Studio 进度页'),

    h1('6 跑工作流（编排页）'),
    h2('6.1 步骤'),
    bullet('项目管理新建项目，或直接进入工作流编排'),
    bullet('「填写目标」→ 粘贴需求（如内部工单台）→「写入目标并载入 Deliver」'),
    bullet('确认「内核在线」→ 可选「校验内核」→「运行全流程」'),
    bullet('观察执行日志与八节点：规划→需求→编码→前端→测试↔调试→审查→交付'),
    bullet('若停在人工审批：点「通过」或「驳回」'),
    h2('6.2 注意'),
    note('warn', '填写目标不会自动跑，必须再点「运行全流程」'),
    note('shot', '目标弹窗 + 运行中画布 + DONE'),

    h1('7 运行记录与内核 Agent'),
    bullet('「运行记录」：查看 Run 状态、节点、Token/费用、待审批'),
    bullet('「内核 Agent」：讲解八 Agent 职责与 flash/pro 分模型'),
    note('shot', '运行记录详情'),
    note('fill', '演示 Run ID：____'),

    h1('8 高级项目（可选）'),
    bullet('上传 SRS/DOCX → 创建高级项目'),
    bullet('生成当前期 / 只验收 / 一键生成剩余里程碑'),
    bullet('导出 ZIP 或复制工作区路径'),
    note('shot', '高级项目导出'),

    h1('9 查看产物与导出'),
    h2('9.1 普通 Deliver（工单台示例）'),
    pBody('目录：backend/apps/demo-code-agent/frontend/'),
    bullet('预览：在该目录执行 npx serve -l 5175，或直接打开 index.html'),
    bullet('演示：创建工单、改状态、删除、刷新仍在'),
    bullet('导出：将该文件夹压缩为 ZIP'),
    h2('9.2 大项目 / 高级项目'),
    bullet('workspaces/studio-* 或 workspaces/ap-*'),
    bullet('Studio「下载 ZIP」或高级项目「导出 ZIP」'),
    h2('9.3 对话技能导出'),
    bullet('写作 docx · PPT pptx · 流程图多格式 · 图像下载'),
    note('shot', '工单台页面操作 + 一种导出方式'),

    h1('10 设置与主题'),
    bullet('设置：资料、工作空间偏好、动画、通知'),
    bullet('主题：云雾浅昼（默认）、港湾暮蓝、苔原柔青、暮霞藕粉、陶土暖沙、墨玉静夜'),
    note('shot', '主题切换一张'),

    h1('11 推荐演示脚本（约 10 分钟）'),
    table(
      ['序号', '内容', '时长建议'],
      [
        ['1', '双终端启动，展示内核在线', '1 min'],
        ['2', '登录 + 多用户隔离一句话', '1 min'],
        ['3', '对话技能 1～2 个（写作/流程图）', '2 min'],
        ['4', '编排页跑工单台（或展示已跑完结果）', '3 min'],
        ['5', '打开产物现场操作 + 说明导出', '2 min'],
        ['6', '运行记录回顾 Agent 链（可选高级 ZIP）', '1 min'],
      ],
    ),
    note('fill', '按答辩时长删减第 3/6 步'),

    h1('12 常见问题'),
    table(
      ['现象', '处理'],
      [
        ['点了填写目标没动静', '再点「运行全流程」'],
        ['内核离线', '检查 8787 与 DEEPSEEK_API_KEY'],
        ['找不到 ZIP 按钮', '未开大项目则手动打包 frontend'],
        ['语音/联网/生图失败', '检查对应第三方 Key'],
        ['换账号仍看到旧历史', '应已按 userId 隔离；清站点数据再验'],
      ],
    ),
    note('shot', '可选 FAQ 对应界面'),
  ].join('')
}

const template = await loadTemplateParts()
const outs = []
outs.push(await writeDocx('04-接口设计文档.docx', apiBody(), template))
outs.push(await writeDocx('05-测试文档.docx', testBody(), template))
outs.push(await writeDocx('06-用户操作手册.docx', manualBody(), template))

console.log('Reformatted like SRS outline:')
for (const f of outs) console.log(' ', f)
