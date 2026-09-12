import { useMemo, useState } from 'react'
import { ChevronRight, FileCode2, Folder } from 'lucide-react'
import { cn } from '@/lib/utils'

export type FileTreeNode = {
  name: string
  path: string
  type: 'file' | 'dir'
  children?: FileTreeNode[]
}

/** 把路径列表建成树 */
export function buildFileTree(paths: string[]): FileTreeNode[] {
  type Mutable = {
    name: string
    path: string
    type: 'file' | 'dir'
    children: Map<string, Mutable>
  }
  const root = new Map<string, Mutable>()

  const ensure = (parts: string[], isFile: boolean) => {
    let cursor = root
    let acc = ''
    parts.forEach((part, idx) => {
      const last = idx === parts.length - 1
      acc = acc ? `${acc}/${part}` : part
      if (!cursor.has(part)) {
        cursor.set(part, {
          name: part,
          path: acc,
          type: last && isFile ? 'file' : 'dir',
          children: new Map(),
        })
      }
      const node = cursor.get(part)!
      if (!(last && isFile)) {
        node.type = 'dir'
        cursor = node.children
      }
    })
  }

  for (const raw of paths) {
    const norm = raw.replace(/\\/g, '/').replace(/^\.\//, '').replace(/^\/+/, '')
    if (!norm) continue
    const parts = norm.split('/').filter(Boolean)
    if (!parts.length) continue
    ensure(parts, true)
  }

  const toList = (map: Map<string, Mutable>): FileTreeNode[] =>
    [...map.values()]
      .sort((a, b) => {
        if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
        return a.name.localeCompare(b.name)
      })
      .map((n) => ({
        name: n.name,
        path: n.path,
        type: n.type,
        children: n.type === 'dir' ? toList(n.children) : undefined,
      }))

  return toList(root)
}

function TreeRow({
  node,
  depth,
  onOpenFile,
  activePath,
}: {
  node: FileTreeNode
  depth: number
  onOpenFile?: (path: string) => void
  activePath?: string | null
}) {
  const [open, setOpen] = useState(depth < 2)
  const isDir = node.type === 'dir'
  const active = !isDir && activePath === node.path

  return (
    <div>
      <button
        type="button"
        className={cn(
          'flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-[12px] pressable hover:bg-muted/70',
          !isDir && 'text-foreground/85',
          active && 'bg-primary/10 text-primary',
        )}
        style={{ paddingLeft: 6 + depth * 12 }}
        onClick={() => {
          if (isDir) setOpen((v) => !v)
          else onOpenFile?.(node.path)
        }}
        title={node.path}
      >
        {isDir ? (
          <ChevronRight
            className={cn(
              'size-3 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-90',
            )}
          />
        ) : (
          <span className="size-3 shrink-0" />
        )}
        {isDir ? (
          <Folder className="size-3.5 shrink-0 text-primary/80" />
        ) : (
          <FileCode2 className="size-3.5 shrink-0 text-muted-foreground" />
        )}
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && open && node.children?.length
        ? node.children.map((child) => (
            <TreeRow
              key={child.path}
              node={child}
              depth={depth + 1}
              onOpenFile={onOpenFile}
              activePath={activePath}
            />
          ))
        : null}
    </div>
  )
}

export default function ProjectFileTree({
  paths,
  title = '工程树',
  emptyText = '暂无文件',
  className,
  onOpenFile,
  activePath,
}: {
  paths: string[]
  title?: string
  emptyText?: string
  className?: string
  onOpenFile?: (path: string) => void
  activePath?: string | null
}) {
  const tree = useMemo(() => buildFileTree(paths), [paths])

  return (
    <div
      className={cn(
        'rounded-xl border border-border/80 bg-muted/20 overflow-hidden',
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
        <span className="text-xs font-medium">{title}</span>
        <span className="text-[10px] text-muted-foreground">{paths.length} 项</span>
      </div>
      <div className="max-h-56 overflow-y-auto overscroll-contain px-1 py-1.5">
        {tree.length === 0 ? (
          <p className="px-2 py-3 text-[11px] text-muted-foreground">{emptyText}</p>
        ) : (
          tree.map((n) => (
            <TreeRow
              key={n.path}
              node={n}
              depth={0}
              onOpenFile={onOpenFile}
              activePath={activePath}
            />
          ))
        )}
      </div>
    </div>
  )
}
