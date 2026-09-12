import {
  getPipelineSeed,
  getPipelineTopic,
  readStudioDraft,
} from '@/lib/studio-session'

export type ProjectFile = {
  path: string
  content: string
}

const LANG_EXT: Record<string, string> = {
  html: 'html',
  htm: 'html',
  css: 'css',
  scss: 'scss',
  js: 'js',
  javascript: 'js',
  ts: 'ts',
  typescript: 'ts',
  jsx: 'jsx',
  tsx: 'tsx',
  json: 'json',
  md: 'md',
  markdown: 'md',
  py: 'py',
  python: 'py',
  java: 'java',
  go: 'go',
  rs: 'rs',
  rust: 'rs',
  sql: 'sql',
  sh: 'sh',
  bash: 'sh',
  yml: 'yml',
  yaml: 'yml',
  dockerfile: 'Dockerfile',
  vue: 'vue',
}

function slugify(input: string): string {
  const s = input
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fff-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
  return (s || 'mawp-project').slice(0, 48)
}

function sanitizePath(raw: string): string | null {
  let p = raw.trim().replace(/\\/g, '/').replace(/^\.?\//, '')
  p = p.replace(/^['"`]|['"`]$/g, '')
  if (!p || p.includes('..') || p.startsWith('/') || /^[a-z]:/i.test(p)) {
    return null
  }
  // 去掉明显不是路径的句子
  if (/\s/.test(p) && !p.includes('/')) return null
  if (p.length > 180) return null
  return p
}

type Fence = { lang: string; meta: string; code: string; before: string }

function parseFences(markdown: string): Fence[] {
  const out: Fence[] = []
  const re = /```([^\n`]*)\n([\s\S]*?)```/g
  let m: RegExpExecArray | null
  let last = 0
  while ((m = re.exec(markdown))) {
    const header = (m[1] || '').trim()
    const [lang, ...rest] = header.split(/\s+/)
    out.push({
      lang: (lang || '').toLowerCase(),
      meta: rest.join(' '),
      code: m[2].replace(/\n$/, ''),
      before: markdown.slice(last, m.index),
    })
    last = m.index + m[0].length
  }
  return out
}

function guessPathFromContext(fence: Fence, index: number): string | null {
  const metaPath = sanitizePath(
    fence.meta.replace(/^(file|path|title)[=:]?\s*/i, ''),
  )
  if (metaPath && metaPath.includes('.')) return metaPath

  // ```ts:src/app.ts
  if (fence.lang.includes(':')) {
    const [, maybe] = fence.lang.split(':')
    const p = sanitizePath(maybe || '')
    if (p) return p
  }

  const before = fence.before
  const patterns = [
    /(?:^|\n)(?:#{1,3}\s*)?(?:文件|路径|File|Path)\s*[:：]\s*`?([^\s`\n]+)`?/i,
    /(?:^|\n)(?:#{1,3}\s*)?`([^`\n]+\.[a-z0-9]+)`\s*$/i,
    /(?:^|\n)\s*\/\/\s*(?:file\s*:?\s*)?([^\s]+\.[a-z0-9]+)\s*$/i,
    /(?:^|\n)\s*#\s*([^\s]+\.[a-z0-9]+)\s*$/i,
  ]
  for (const p of patterns) {
    const m = before.match(p)
    if (m?.[1]) {
      const path = sanitizePath(m[1])
      if (path) return path
    }
  }

  // 代码首行注释：// src/foo.ts 或 <!-- index.html -->
  const first = fence.code.split('\n')[0] || ''
  const lineHit = first.match(
    /(?:\/\/|#|\/\*|--)\s*(?:file\s*:?\s*)?([a-z0-9_./-]+\.[a-z0-9]+)/i,
  )
  if (lineHit?.[1]) {
    const path = sanitizePath(lineHit[1])
    if (path) return path
  }

  const ext = LANG_EXT[fence.lang] || (fence.lang.length <= 4 ? fence.lang : '')
  if (!ext) return null
  if (ext === 'html') return index === 0 ? 'index.html' : `src/page-${index + 1}.html`
  if (ext === 'css') return index === 0 ? 'styles.css' : `src/styles-${index + 1}.css`
  if (ext === 'js') return `src/main-${index + 1}.js`
  if (ext === 'ts') return `src/main-${index + 1}.ts`
  if (ext === 'tsx') return `src/App-${index + 1}.tsx`
  if (ext === 'py') return `src/main_${index + 1}.py`
  if (ext === 'Dockerfile') return 'Dockerfile'
  return `src/snippet-${index + 1}.${ext}`
}

function uniquePath(path: string, used: Set<string>): string {
  if (!used.has(path)) {
    used.add(path)
    return path
  }
  const i = path.lastIndexOf('.')
  const base = i > 0 ? path.slice(0, i) : path
  const ext = i > 0 ? path.slice(i) : ''
  let n = 2
  while (used.has(`${base}-${n}${ext}`)) n += 1
  const next = `${base}-${n}${ext}`
  used.add(next)
  return next
}

export function buildProjectBundle(): {
  projectName: string
  files: ProjectFile[]
} {
  const topic = getPipelineTopic() || getPipelineSeed() || '智流项目'
  const projectName = slugify(topic)
  const requirement = readStudioDraft('requirement')
  const architecture = readStudioDraft('architecture')
  const code = readStudioDraft('code')
  const test = readStudioDraft('test')
  const deploy = readStudioDraft('deploy')

  const files: ProjectFile[] = []
  const used = new Set<string>()

  const push = (path: string, content: string) => {
    const p = uniquePath(path, used)
    files.push({ path: p, content: content.endsWith('\n') ? content : content + '\n' })
  }

  push(
    'README.md',
    `# ${topic}

> 由智流 MAWP 一键导出

## 来源目标
${getPipelineSeed() || topic}

## 目录说明
- \`docs/\` 需求、架构、测试、部署文档
- \`src/\` 与根目录下的可运行源码（从代码阶段抽取）

## 快速开始
1. 若根目录有 \`index.html\`，用浏览器直接打开或起静态服务
2. 若有 \`package.json\`，执行 \`npm install && npm run dev\`
3. 其余语言请按 \`docs/\` 中的说明启动

导出时间：${new Date().toLocaleString()}
`,
  )

  if (requirement?.output?.trim()) {
    push('docs/01-requirement.md', requirement.output)
  }
  if (architecture?.output?.trim()) {
    push('docs/02-architecture.md', architecture.output)
  }
  if (test?.output?.trim()) {
    push('docs/03-test-report.md', test.output)
  }
  if (deploy?.output?.trim()) {
    push('docs/04-deploy.md', deploy.output)
  }

  const codeMd = code?.output?.trim() || ''
  if (codeMd) {
    push('docs/00-code-source.md', codeMd)
    const fences = parseFences(codeMd)
    let codeFiles = 0
    fences.forEach((fence, i) => {
      if (!fence.code.trim()) return
      // 跳过纯说明性空语言且很短的块
      const path = guessPathFromContext(fence, i)
      if (!path) return
      push(path, fence.code)
      codeFiles += 1
    })

    // 没有任何路径可猜时：整份代码落成单文件
    if (codeFiles === 0) {
      if (/<!doctype html/i.test(codeMd) || /<html[\s>]/i.test(codeMd)) {
        push('index.html', codeMd)
      } else {
        push('src/generated-code.md', codeMd)
      }
    }
  }

  // 保证至少有一个可打开的入口提示
  const hasEntry = files.some((f) =>
    /^(index\.html|package\.json|src\/)/.test(f.path),
  )
  if (!hasEntry) {
    push(
      'src/.gitkeep',
      '# 代码阶段尚未生成可抽取源码，请回到「代码编写」重新生成后再导出\n',
    )
  }

  // 若有 html 入口但没有 package.json，补一个极简静态说明（不强制）
  const hasHtml = files.some((f) => f.path.endsWith('.html'))
  const hasPkg = files.some((f) => f.path === 'package.json')
  if (hasHtml && !hasPkg) {
    push(
      'package.json',
      JSON.stringify(
        {
          name: projectName,
          private: true,
          version: '1.0.0',
          description: topic,
          scripts: {
            start: 'npx --yes serve .',
            preview: 'npx --yes serve .',
          },
        },
        null,
        2,
      ),
    )
  }

  push(
    'mawp-export.json',
    JSON.stringify(
      {
        tool: '智流 MAWP',
        projectName,
        topic,
        seed: getPipelineSeed(),
        exportedAt: new Date().toISOString(),
        stages: {
          requirement: Boolean(requirement?.output),
          architecture: Boolean(architecture?.output),
          code: Boolean(code?.output),
          test: Boolean(test?.output),
          deploy: Boolean(deploy?.output),
        },
        fileCount: files.length + 1,
      },
      null,
      2,
    ),
  )

  return { projectName, files }
}

export function summarizeTree(files: ProjectFile[]): string {
  const paths = files.map((f) => f.path).sort()
  const lines: string[] = []
  for (const p of paths) {
    const parts = p.split('/')
    const depth = parts.length - 1
    const name = parts[parts.length - 1]
    lines.push(`${'  '.repeat(depth)}${depth ? '└─ ' : ''}${name}`)
  }
  return lines.join('\n')
}
