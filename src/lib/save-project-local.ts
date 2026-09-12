import JSZip from 'jszip'
import {
  buildProjectBundle,
  summarizeTree,
  type ProjectFile,
} from '@/lib/export-project'

export type SaveProjectResult =
  | {
      mode: 'folder'
      projectName: string
      rootName: string
      fileCount: number
      tree: string
    }
  | {
      mode: 'zip'
      projectName: string
      fileName: string
      fileCount: number
      tree: string
    }

type DirHandle = FileSystemDirectoryHandle

async function ensureDir(
  root: DirHandle,
  segments: string[],
): Promise<DirHandle> {
  let cur = root
  for (const seg of segments) {
    cur = await cur.getDirectoryHandle(seg, { create: true })
  }
  return cur
}

async function writeFilesToDirectory(
  root: DirHandle,
  files: ProjectFile[],
) {
  for (const file of files) {
    const parts = file.path.split('/').filter(Boolean)
    const name = parts.pop()!
    const dir = parts.length ? await ensureDir(root, parts) : root
    const fh = await dir.getFileHandle(name, { create: true })
    const writable = await fh.createWritable()
    await writable.write(file.content)
    await writable.close()
  }
}

function canUseDirectoryPicker(): boolean {
  return typeof window !== 'undefined' && 'showDirectoryPicker' in window
}

async function downloadZip(projectName: string, files: ProjectFile[]) {
  const zip = new JSZip()
  const root = zip.folder(projectName)
  if (!root) throw new Error('无法创建压缩包')
  for (const file of files) {
    root.file(file.path, file.content)
  }
  const blob = await zip.generateAsync({ type: 'blob' })
  const fileName = `${projectName}.zip`
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  a.click()
  URL.revokeObjectURL(url)
  return fileName
}

/**
 * 一键保存项目：
 * 1) 支持时：让用户选本地目录，自动创建项目文件夹与文件结构
 * 2) 否则：下载 ZIP
 */
export async function saveProjectToLocal(options?: {
  preferZip?: boolean
}): Promise<SaveProjectResult> {
  const { projectName, files } = buildProjectBundle()
  const tree = summarizeTree(files)

  if (!options?.preferZip && canUseDirectoryPicker()) {
    try {
      const picker = (
        window as Window & {
          showDirectoryPicker: (opts?: {
            mode?: 'read' | 'readwrite'
          }) => Promise<DirHandle>
        }
      ).showDirectoryPicker
      const parent = await picker({ mode: 'readwrite' })
      const projectDir = await parent.getDirectoryHandle(projectName, {
        create: true,
      })
      await writeFilesToDirectory(projectDir, files)
      return {
        mode: 'folder',
        projectName,
        rootName: projectName,
        fileCount: files.length,
        tree,
      }
    } catch (err) {
      // 用户取消则抛出；权限/不支持则回落 ZIP
      if ((err as Error)?.name === 'AbortError') throw err
    }
  }

  const fileName = await downloadZip(projectName, files)
  return {
    mode: 'zip',
    projectName,
    fileName,
    fileCount: files.length,
    tree,
  }
}

export function previewProjectTree(): {
  projectName: string
  fileCount: number
  tree: string
} {
  const { projectName, files } = buildProjectBundle()
  return {
    projectName,
    fileCount: files.length,
    tree: summarizeTree(files),
  }
}
