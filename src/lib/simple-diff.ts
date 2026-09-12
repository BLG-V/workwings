/** 极简行级 diff（对照上一次预览内容） */

export type DiffLine = {
  type: 'same' | 'add' | 'del'
  text: string
}

export function buildLineDiff(before: string, after: string): DiffLine[] {
  const a = before.replace(/\r\n/g, '\n').split('\n')
  const b = after.replace(/\r\n/g, '\n').split('\n')
  // LCS 对大文件过重：用短文件精确、长文件窗口对齐
  if (a.length * b.length > 80_000) {
    return roughDiff(a, b)
  }
  return lcsDiff(a, b)
}

function roughDiff(a: string[], b: string[]): DiffLine[] {
  const out: DiffLine[] = []
  const max = Math.max(a.length, b.length)
  for (let i = 0; i < max; i += 1) {
    const left = a[i]
    const right = b[i]
    if (left === undefined) out.push({ type: 'add', text: right })
    else if (right === undefined) out.push({ type: 'del', text: left })
    else if (left === right) out.push({ type: 'same', text: left })
    else {
      out.push({ type: 'del', text: left })
      out.push({ type: 'add', text: right })
    }
  }
  return out
}

function lcsDiff(a: string[], b: string[]): DiffLine[] {
  const n = a.length
  const m = b.length
  const dp: number[][] = Array.from({ length: n + 1 }, () =>
    Array(m + 1).fill(0),
  )
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      dp[i][j] =
        a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const out: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ type: 'same', text: a[i] })
      i += 1
      j += 1
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: 'del', text: a[i] })
      i += 1
    } else {
      out.push({ type: 'add', text: b[j] })
      j += 1
    }
  }
  while (i < n) {
    out.push({ type: 'del', text: a[i] })
    i += 1
  }
  while (j < m) {
    out.push({ type: 'add', text: b[j] })
    j += 1
  }
  return out
}
