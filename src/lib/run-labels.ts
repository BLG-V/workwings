/** Runs / 编排页共用的失败分类中文标签 */

export const ERROR_CATEGORY_LABEL: Record<string, string> = {
  syntax_error: '语法错误',
  import_error: '导入错误',
  route_error: '路由/入口',
  build_error: '构建失败',
  runtime_error: '运行时',
  timeout: '超时',
  transient: '瞬时故障',
  test_failed: '测试未过',
  review_blocking: '审查拦截',
  max_steps: '步数上限',
  quota: '余额不足',
  auth_error: '密钥无效',
  missing_file: '缺文件',
  unknown: '未分类',
}

export function labelErrorCategory(cat?: string | null): string {
  if (!cat) return ''
  return ERROR_CATEGORY_LABEL[cat] || cat
}

export function formatTok(n?: number | null): string {
  if (n == null || !Number.isFinite(n) || n <= 0) return '—'
  if (n >= 10_000) return `${Math.round(n / 1000)}k`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export function formatCnyLite(n?: number | null): string {
  if (n == null || !Number.isFinite(n)) return '—'
  if (n === 0) return '¥0'
  if (n < 0.01) return `¥${n.toFixed(4)}`
  return `¥${n.toFixed(2)}`
}
