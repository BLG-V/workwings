import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FileCode2,
  Folder,
  ChevronRight,
  Save,
  RotateCcw,
  Download,
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Eye,
  Code2,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  listProjectFiles,
  readProjectFile,
  saveProjectFile,
  downloadProjectZip,
} from '@/lib/mawp-api'
import { buildFileTree, type FileTreeNode } from './ProjectFileTree'
import { toast } from 'sonner'

interface ProjectExplorerProps {
  projectRoot: string
  className?: string
  onClose?: () => void
}

const TEXT_EXTENSIONS = new Set([
  '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.md', '.txt', '.yaml', '.yml',
  '.html', '.css', '.scss', '.vue', '.sh', '.env', '.toml', '.cfg', '.ini',
  '.conf', '.xml', '.sql', '.graphql', '.gql', '.dockerfile', '.gitignore',
])

function isTextFile(path: string): boolean {
  const lower = path.toLowerCase()
  if (lower.endsWith('.dockerfile') || lower.endsWith('.gitignore')) return true
  const ext = lower.substring(lower.lastIndexOf('.'))
  return TEXT_EXTENSIONS.has(ext)
}

function fileIcon(path: string) {
  const lower = path.toLowerCase()
  if (lower.endsWith('.py')) return <FileCode2 className="size-3.5 text-yellow-500" />
  if (lower.endsWith('.ts') || lower.endsWith('.tsx')) return <FileCode2 className="size-3.5 text-blue-500" />
  if (lower.endsWith('.js') || lower.endsWith('.jsx')) return <FileCode2 className="size-3.5 text-yellow-400" />
  if (lower.endsWith('.json')) return <FileCode2 className="size-3.5 text-green-500" />
  if (lower.endsWith('.md')) return <FileText className="size-3.5 text-muted-foreground" />
  if (lower.endsWith('.html')) return <FileCode2 className="size-3.5 text-orange-500" />
  if (lower.endsWith('.css') || lower.endsWith('.scss')) return <FileCode2 className="size-3.5 text-pink-500" />
  if (lower.endsWith('.sh')) return <FileCode2 className="size-3.5 text-green-600" />
  if (lower.endsWith('.yaml') || lower.endsWith('.yml')) return <FileCode2 className="size-3.5 text-purple-500" />
  return <FileCode2 className="size-3.5 text-muted-foreground" />
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
  const [open, setOpen] = useState(depth < 1)
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
          fileIcon(node.path)
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

export default function ProjectExplorer({
  projectRoot,
  className,
  onClose,
}: ProjectExplorerProps) {
  const [paths, setPaths] = useState<string[]>([])
  const [tree, setTree] = useState<FileTreeNode[]>([])
  const [activePath, setActivePath] = useState<string | null>(null)
  const [content, setContent] = useState('')
  const [originalContent, setOriginalContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [view, setView] = useState<'code' | 'preview'>('code')
  const [downloading, setDownloading] = useState(false)
  const [truncated, setTruncated] = useState(false)

  const loadTree = useCallback(async () => {
    if (!projectRoot) return
    try {
      const res = await listProjectFiles(projectRoot)
      setPaths(res.paths)
      setTree(buildFileTree(res.paths))
      setTruncated(res.truncated)
    } catch {
      setPaths([])
      setTree([])
    }
  }, [projectRoot])

  useEffect(() => {
    loadTree()
  }, [loadTree])

  const openFile = useCallback(
    async (path: string) => {
      if (!isTextFile(path)) {
        toast.message('暂不支持预览此文件类型', {
          description: path,
        })
        return
      }
      setLoading(true)
      setActivePath(path)
      setContent('')
      setDirty(false)
      try {
        const res = await readProjectFile(projectRoot, path)
        setContent(res.content)
        setOriginalContent(res.content)
        setView('code')
      } catch (err) {
        toast.error(err instanceof Error ? err.message : '读取文件失败')
        setActivePath(null)
      } finally {
        setLoading(false)
      }
    },
    [projectRoot],
  )

  const handleSave = async () => {
    if (!activePath) return
    setSaving(true)
    try {
      await saveProjectFile(projectRoot, activePath, content)
      setOriginalContent(content)
      setDirty(false)
      toast.success('文件已保存')
      await loadTree()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setContent(originalContent)
    setDirty(false)
  }

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const blob = await downloadProjectZip(projectRoot)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${projectRoot.split('/').pop() || 'project'}.zip`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('项目 ZIP 已下载')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '下载失败')
    } finally {
      setDownloading(false)
    }
  }

  const handleContentChange = (value: string) => {
    setContent(value)
    setDirty(value !== originalContent)
  }

  return (
    <div
      className={cn(
        'flex h-full overflow-hidden rounded-2xl border border-border bg-card',
        className,
      )}
    >
      {/* 左侧文件树 */}
      <div className="flex w-56 shrink-0 flex-col border-r border-border/60">
        <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
          <span className="text-xs font-medium">工程文件</span>
          <div className="flex items-center gap-1">
            <Button
              size="icon"
              variant="ghost"
              className="size-6"
              onClick={loadTree}
              title="刷新"
            >
              <RotateCcw className="size-3" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="size-6"
              onClick={handleDownload}
              disabled={downloading}
              title="下载 ZIP"
            >
              {downloading ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <Download className="size-3" />
              )}
            </Button>
            {onClose && (
              <Button
                size="icon"
                variant="ghost"
                className="size-6"
                onClick={onClose}
                title="关闭"
              >
                <X className="size-3" />
              </Button>
            )}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-1 py-1.5">
          {tree.length === 0 ? (
            <p className="px-2 py-3 text-[11px] text-muted-foreground">
              暂无文件
            </p>
          ) : (
            tree.map((n) => (
              <TreeRow
                key={n.path}
                node={n}
                depth={0}
                onOpenFile={openFile}
                activePath={activePath}
              />
            ))
          )}
          {truncated && (
            <p className="px-2 py-1 text-[10px] text-muted-foreground">
              文件数过多，已截断
            </p>
          )}
        </div>
        <div className="border-t border-border/60 px-3 py-1.5">
          <p className="text-[10px] text-muted-foreground truncate" title={projectRoot}>
            {projectRoot}
          </p>
          <p className="text-[10px] text-muted-foreground">{paths.length} 个文件</p>
        </div>
      </div>

      {/* 右侧编辑器 */}
      <div className="flex flex-1 flex-col">
        {activePath ? (
          <>
            <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
              <div className="flex items-center gap-2 min-w-0">
                {fileIcon(activePath)}
                <span className="text-xs font-medium truncate" title={activePath}>
                  {activePath}
                </span>
                {dirty && (
                  <Badge variant="outline" className="text-[9px] text-amber-600 border-amber-300">
                    未保存
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7"
                  onClick={() => setView(view === 'code' ? 'preview' : 'code')}
                >
                  {view === 'code' ? (
                    <Eye className="size-3 mr-1" />
                  ) : (
                    <Code2 className="size-3 mr-1" />
                  )}
                  {view === 'code' ? '预览' : '编辑'}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7"
                  onClick={handleReset}
                  disabled={!dirty || saving}
                >
                  <RotateCcw className="size-3 mr-1" />
                  还原
                </Button>
                <Button
                  size="sm"
                  className="h-7"
                  onClick={handleSave}
                  disabled={!dirty || saving || view !== 'code'}
                >
                  {saving ? (
                    <Loader2 className="size-3 mr-1 animate-spin" />
                  ) : (
                    <Save className="size-3 mr-1" />
                  )}
                  保存
                </Button>
              </div>
            </div>
            <div className="flex-1 overflow-hidden">
              {loading ? (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  <Loader2 className="size-5 animate-spin" />
                </div>
              ) : view === 'code' ? (
                <textarea
                  value={content}
                  onChange={(e) => handleContentChange(e.target.value)}
                  className="h-full w-full resize-none bg-background/50 p-3 font-mono text-xs leading-relaxed focus:outline-none"
                  spellCheck={false}
                />
              ) : (
                <div className="h-full overflow-y-auto p-4">
                  {activePath.endsWith('.md') ? (
                    <div className="prose prose-sm max-w-none">
                      <pre className="whitespace-pre-wrap text-xs">{content}</pre>
                    </div>
                  ) : (
                    <pre className="whitespace-pre-wrap text-xs font-mono leading-relaxed text-muted-foreground">
                      {content}
                    </pre>
                  )}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
            <FileCode2 className="size-8 mb-3 text-primary/50" />
            <p className="text-sm">选择左侧文件以查看或编辑</p>
            <p className="text-xs mt-1">支持在线编辑并保存回工作区</p>
          </div>
        )}
      </div>
    </div>
  )
}
