import { useNavigate } from 'react-router-dom'
import { OAUTH_PROVIDERS } from '@/lib/auth'
import { cn } from '@/lib/utils'

export default function OAuthButtons({
  from = '/chat',
  variant = 'row',
}: {
  from?: string
  /** row：一行三枚紧凑按钮；stack：纵向大按钮 */
  variant?: 'row' | 'stack'
}) {
  const navigate = useNavigate()

  if (variant === 'stack') {
    return (
      <div className="grid gap-2">
        {OAUTH_PROVIDERS.map((p) => (
          <button
            key={p.id}
            type="button"
            className={cn(
              'pressable flex h-10 w-full items-center justify-center gap-2 rounded-xl text-sm font-medium transition-colors',
              p.color,
            )}
            onClick={() => navigate(`/oauth/${p.id}`, { state: { from } })}
          >
            <ProviderGlyph id={p.id} />
            {p.label}
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-2">
      {OAUTH_PROVIDERS.map((p) => (
        <button
          key={p.id}
          type="button"
          title={p.desc}
          className={cn(
            'pressable flex h-11 flex-col items-center justify-center gap-1 rounded-xl text-[11px] font-medium transition-colors',
            p.color,
          )}
          onClick={() => navigate(`/oauth/${p.id}`, { state: { from } })}
        >
          <ProviderGlyph id={p.id} />
          <span>{p.label}</span>
        </button>
      ))}
    </div>
  )
}

function ProviderGlyph({ id }: { id: string }) {
  if (id === 'github') {
    return (
      <svg viewBox="0 0 24 24" className="size-4 fill-current" aria-hidden>
        <path d="M12 .5C5.37.5 0 5.87 0 12.5c0 5.3 3.44 9.79 8.21 11.37.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.1-.75.08-.74.08-.74 1.22.09 1.86 1.25 1.86 1.25 1.08 1.85 2.83 1.32 3.52 1.01.11-.78.42-1.32.76-1.62-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.12-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.29-1.55 3.3-1.23 3.3-1.23.66 1.65.24 2.87.12 3.17.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.62-5.49 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.7.83.58A12.01 12.01 0 0 0 24 12.5C24 5.87 18.63.5 12 .5Z" />
      </svg>
    )
  }
  if (id === 'google') {
    return (
      <svg viewBox="0 0 24 24" className="size-4" aria-hidden>
        <path
          fill="#EA4335"
          d="M12 10.2v3.9h5.5c-.2 1.3-1.6 3.9-5.5 3.9-3.3 0-6-2.7-6-6s2.7-6 6-6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.9 3.5 14.7 2.5 12 2.5 6.8 2.5 2.5 6.8 2.5 12S6.8 21.5 12 21.5c5.5 0 9.1-3.9 9.1-9.3 0-.6-.1-1.1-.2-1.6H12z"
        />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" className="size-4 fill-current" aria-hidden>
      <path d="M9.5 4.2c-3.7.1-6.7 2.8-6.7 6.2 0 2.1 1.2 4 3.1 5.2l-.8 2.4 2.7-1.4c.7.2 1.5.3 2.2.3h.2c3.7 0 6.7-2.8 6.7-6.2S13.2 4.2 9.5 4.2zm3.6 8.3h-1.4v1.4H10.4v-1.4H9v-1.3h1.4V9.8h1.3v1.4h1.4v1.3zm5.7-3.1c.1-.4.1-.8.1-1.2 0-3.4-3.3-6.2-7.4-6.2-.6 0-1.2.1-1.7.2C13.6 3.2 17 5.7 17 9c0 2-.9 3.8-2.4 5 2.6-.2 4.9-1.8 5.8-4.6z" />
    </svg>
  )
}
