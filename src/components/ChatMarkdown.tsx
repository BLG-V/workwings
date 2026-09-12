import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import GeneratedImageFrame from '@/components/GeneratedImageFrame'

interface ChatMarkdownProps {
  content: string
  className?: string
}

function textOf(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (node && typeof node === 'object' && 'props' in node) {
    const props = (node as { props?: { children?: ReactNode } }).props
    return textOf(props?.children)
  }
  return ''
}

export default function ChatMarkdown({ content, className = '' }: ChatMarkdownProps) {
  return (
    <div className={`chat-prose ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="chat-prose-h1">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="chat-prose-h2">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="chat-prose-h3">{children}</h3>
          ),
          p: ({ children }) => {
            const raw = textOf(children).trim()
            const isOk = raw.startsWith('✅')
            const isBad = raw.startsWith('❌')
            // 段落里只有一张图时去掉多余外边距
            return (
              <p
                className={
                  isOk
                    ? 'chat-prose-p chat-prose-cue-ok'
                    : isBad
                      ? 'chat-prose-p chat-prose-cue-bad'
                      : 'chat-prose-p'
                }
              >
                {children}
              </p>
            )
          },
          ul: ({ children }) => <ul className="chat-prose-ul">{children}</ul>,
          ol: ({ children }) => <ol className="chat-prose-ol">{children}</ol>,
          li: ({ children }) => <li className="chat-prose-li">{children}</li>,
          strong: ({ children }) => (
            <strong className="chat-prose-strong">{children}</strong>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="chat-prose-a"
            >
              {children}
            </a>
          ),
          img: ({ src, alt }) => (
            <GeneratedImageFrame src={src} alt={alt || ''} />
          ),
          blockquote: ({ children }) => {
            const raw = textOf(children)
            const bad = raw.includes('❌')
            return (
              <blockquote
                className={
                  bad ? 'chat-prose-quote chat-prose-quote-bad' : 'chat-prose-quote'
                }
              >
                {children}
              </blockquote>
            )
          },
          code: ({ className: codeClass, children }) => {
            const isBlock = Boolean(codeClass)
            if (isBlock) {
              return <code className={codeClass}>{children}</code>
            }
            return <code className="chat-prose-code">{children}</code>
          },
          pre: ({ children }) => <pre className="chat-prose-pre">{children}</pre>,
          hr: () => <hr className="chat-prose-hr" />,
          table: ({ children }) => (
            <div className="chat-prose-table-wrap">
              <table className="chat-prose-table">{children}</table>
            </div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
