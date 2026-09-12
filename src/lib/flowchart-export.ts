import { jsPDF } from 'jspdf'
import mermaid from 'mermaid'
import type { FlowchartPayload } from '@/lib/flowchart'
import { flowchartToMermaid } from '@/lib/flowchart'

export type FlowchartExportFormat =
  | 'svg'
  | 'png'
  | 'pdf'
  | 'mmd'
  | 'json'
  | 'drawio'

export const FLOWCHART_EXPORT_OPTIONS: Array<{
  id: FlowchartExportFormat
  label: string
  hint: string
}> = [
  { id: 'png', label: 'PNG 图片', hint: '微信 / 飞书 / PPT' },
  { id: 'svg', label: 'SVG 矢量', hint: 'Word / 设计工具' },
  { id: 'pdf', label: 'PDF', hint: '正式交付' },
  { id: 'drawio', label: 'Draw.io', hint: 'diagrams.net 继续改' },
  { id: 'mmd', label: 'Mermaid', hint: 'Markdown / 语雀' },
  { id: 'json', label: 'JSON', hint: '备份 / 程序' },
]

let mermaidReady = false
function ensureMermaid() {
  if (mermaidReady) return
  mermaid.initialize({
    startOnLoad: false,
    theme: 'neutral',
    securityLevel: 'loose',
    flowchart: { curve: 'basis', htmlLabels: true },
  })
  mermaidReady = true
}

function safeName(title: string) {
  return (title || '流程图').replace(/[\\/:*?"<>|]/g, '_').slice(0, 60)
}

function triggerDownload(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function svgToXmlDocument(svg: string): string {
  if (svg.includes('xmlns=')) return svg
  return svg.replace(
    /<svg\b/,
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"',
  )
}

async function renderSvg(doc: FlowchartPayload): Promise<string> {
  ensureMermaid()
  const code = flowchartToMermaid(doc)
  const id = `export-${Math.random().toString(36).slice(2, 10)}`
  const { svg } = await mermaid.render(id, code)
  return svgToXmlDocument(svg)
}

function readSvgSize(svg: string): { w: number; h: number } {
  const view = svg.match(/viewBox=["']([^"']+)["']/i)
  if (view) {
    const parts = view[1].trim().split(/[\s,]+/).map(Number)
    if (parts.length >= 4 && parts[2] > 0 && parts[3] > 0) {
      return { w: parts[2], h: parts[3] }
    }
  }
  const wm = svg.match(/\bwidth=["']([\d.]+)/i)
  const hm = svg.match(/\bheight=["']([\d.]+)/i)
  return {
    w: wm ? Number(wm[1]) : 960,
    h: hm ? Number(hm[1]) : 640,
  }
}

async function svgToPngDataUrl(svg: string, scale = 2): Promise<string> {
  const { w, h } = readSvgSize(svg)
  const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error('SVG 转图片失败'))
      el.src = url
    })
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(w * scale))
    canvas.height = Math.max(1, Math.round(h * scale))
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('画布不可用')
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/png')
  } finally {
    URL.revokeObjectURL(url)
  }
}

async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
  const res = await fetch(dataUrl)
  return res.blob()
}

function escapeXml(s: string) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** diagrams.net / draw.io 可打开的 .drawio */
export function flowchartToDrawio(doc: FlowchartPayload): string {
  const cells: string[] = [
    `<mxCell id="0"/>`,
    `<mxCell id="1" parent="0"/>`,
  ]

  for (const n of doc.nodes) {
    const x = Math.round(n.x ?? 40)
    const y = Math.round(n.y ?? 40)
    const w = n.type === 'decision' ? 140 : 160
    const h = n.type === 'decision' ? 80 : 56
    let style =
      'rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#666666;'
    if (n.type === 'start' || n.type === 'end') {
      style =
        'ellipse;whiteSpace=wrap;html=1;fillColor=#e8f5e9;strokeColor=#2e7d32;'
    } else if (n.type === 'decision') {
      style =
        'rhombus;whiteSpace=wrap;html=1;fillColor=#fff8e1;strokeColor=#f9a825;'
    } else if (n.type === 'io') {
      style =
        'shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fillColor=#e3f2fd;strokeColor=#1565c0;'
    }
    cells.push(
      `<mxCell id="${escapeXml(n.id)}" value="${escapeXml(n.label)}" style="${style}" vertex="1" parent="1"><mxGeometry x="${x}" y="${y}" width="${w}" height="${h}" as="geometry"/></mxCell>`,
    )
  }

  for (const e of doc.edges) {
    const label = e.label ? `value="${escapeXml(e.label)}"` : 'value=""'
    cells.push(
      `<mxCell id="${escapeXml(e.id)}" ${label} style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;endFill=1;" edge="1" parent="1" source="${escapeXml(e.source)}" target="${escapeXml(e.target)}"><mxGeometry relative="1" as="geometry"/></mxCell>`,
    )
  }

  return `<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="${new Date().toISOString()}" agent="AgentFlow" version="22.0.0">
  <diagram id="flowchart" name="${escapeXml(doc.title || '流程图')}">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1169" pageHeight="827">
      <root>
        ${cells.join('\n        ')}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
`
}

export async function exportFlowchart(
  doc: FlowchartPayload,
  format: FlowchartExportFormat,
): Promise<void> {
  const base = safeName(doc.title)

  if (format === 'json') {
    triggerDownload(
      `${base}.json`,
      new Blob([JSON.stringify(doc, null, 2)], {
        type: 'application/json;charset=utf-8',
      }),
    )
    return
  }

  if (format === 'mmd') {
    triggerDownload(
      `${base}.mmd`,
      new Blob([flowchartToMermaid(doc)], {
        type: 'text/plain;charset=utf-8',
      }),
    )
    return
  }

  if (format === 'drawio') {
    triggerDownload(
      `${base}.drawio`,
      new Blob([flowchartToDrawio(doc)], {
        type: 'application/xml;charset=utf-8',
      }),
    )
    return
  }

  const svg = await renderSvg(doc)

  if (format === 'svg') {
    triggerDownload(
      `${base}.svg`,
      new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }),
    )
    return
  }

  const pngDataUrl = await svgToPngDataUrl(svg, 2)

  if (format === 'png') {
    triggerDownload(`${base}.png`, await dataUrlToBlob(pngDataUrl))
    return
  }

  if (format === 'pdf') {
    const { w, h } = readSvgSize(svg)
    const landscape = w >= h
    const pdf = new jsPDF({
      orientation: landscape ? 'landscape' : 'portrait',
      unit: 'pt',
      format: 'a4',
    })
    const pageW = pdf.internal.pageSize.getWidth()
    const pageH = pdf.internal.pageSize.getHeight()
    const margin = 28
    const maxW = pageW - margin * 2
    const maxH = pageH - margin * 2
    const ratio = Math.min(maxW / w, maxH / h)
    const drawW = w * ratio
    const drawH = h * ratio
    const x = (pageW - drawW) / 2
    const y = (pageH - drawH) / 2
    pdf.setFontSize(12)
    pdf.text(doc.title || '流程图', margin, 22)
    pdf.addImage(pngDataUrl, 'PNG', x, Math.max(y, 32), drawW, drawH)
    pdf.save(`${base}.pdf`)
    return
  }
}
