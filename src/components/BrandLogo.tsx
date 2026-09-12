import { cn } from '@/lib/utils'

type BrandLogoProps = {
  className?: string
  /** Icon only, or mark with wordmark. */
  variant?: 'icon' | 'mark'
  /** Icon size, defaults to 40. */
  size?: number
  title?: string
}

/** WorkWings: delivery control mark with flow lines. */
export function BrandMark({
  className,
  size = 40,
  title = 'WorkWings',
}: Omit<BrandLogoProps, 'variant'>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('shrink-0 text-foreground', className)}
      role="img"
      aria-label={title}
    >
      <title>{title}</title>
      <circle
        cx="32"
        cy="32"
        r="28.5"
        stroke="currentColor"
        strokeWidth="2.6"
      />
      <path
        d="M31 15.2
           C27.8 14.6 24.8 15.2 22.6 16.8
           C20.2 15.8 17.4 16.6 16.2 18.8
           C14.2 19.6 13.2 22 13.6 24.4
           C12.2 26.2 12.2 28.8 13.4 30.8
           C12.4 33 12.8 35.6 14.4 37.4
           C14.2 39.8 15.6 42.2 17.8 43.4
           C19 45.6 21.6 46.8 24.4 46.4
           C26.4 47.8 29 47.6 31 46.2
           C31.4 45.8 31.5 45.2 31.5 44.6
           V17.2
           C31.5 16.2 31.4 15.4 31 15.2Z"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <path
        d="M18.8 22.4C21.6 20.8 25 21.2 27.8 23"
        stroke="currentColor"
        strokeWidth="1.85"
        strokeLinecap="round"
      />
      <path
        d="M17.2 28.2C20.4 26.6 24.2 27 27.4 29"
        stroke="currentColor"
        strokeWidth="1.85"
        strokeLinecap="round"
      />
      <path
        d="M18.4 34.4C21.4 33 24.6 33.4 27.4 35.4"
        stroke="currentColor"
        strokeWidth="1.85"
        strokeLinecap="round"
      />
      <path
        d="M21.2 40.2C23.8 39 26.2 39.4 28.2 40.8"
        stroke="currentColor"
        strokeWidth="1.85"
        strokeLinecap="round"
      />
      <path
        d="M34 23.6C37.6 21 41.2 26.2 44.8 23.6C48.2 21.2 51.2 25 54.2 22.8"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M34 32C37.6 29.4 41.2 34.6 44.8 32C48.2 29.6 51.2 33.4 54.2 31.2"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M34 40.4C37.6 37.8 41.2 43 44.8 40.4C48.2 38 51.2 41.8 54.2 39.6"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="32.2" cy="32" r="1.4" fill="currentColor" />
    </svg>
  )
}

/** Horizontal wordmark: icon | WorkWings */
export default function BrandLogo({
  className,
  variant = 'mark',
  size = 40,
  title = 'WorkWings',
}: BrandLogoProps) {
  if (variant === 'icon') {
    return <BrandMark className={className} size={size} title={title} />
  }

  const nameSize =
    size >= 96
      ? 'text-4xl md:text-[2.75rem]'
      : size >= 64
        ? 'text-3xl'
        : size >= 48
          ? 'text-[1.35rem]'
          : 'text-lg'
  const engSize =
    size >= 96
      ? 'text-2xl md:text-3xl'
      : size >= 64
        ? 'text-xl'
        : size >= 48
          ? 'text-base'
          : 'text-sm'
  const dividerH = Math.round(size * 0.72)
  const gap = size >= 64 ? 'gap-3.5' : 'gap-2.5'

  return (
    <div
      className={cn(
        'inline-flex items-center min-w-0 overflow-visible text-foreground',
        gap,
        className,
      )}
      role="img"
      aria-label={title}
    >
      <BrandMark size={size} title={title} />
      <span
        aria-hidden
        className="shrink-0 bg-foreground/90"
        style={{ width: 1.5, height: dividerH }}
      />
      <span
        className={cn(
          'inline-flex items-stretch gap-[0.35em] min-w-0 overflow-visible',
          nameSize,
        )}
      >
        <span className="flex items-center font-display font-bold tracking-tight leading-none">
          Work
        </span>
        <span
          className={cn(
            'flex items-center font-semibold tracking-[0.04em] text-foreground leading-none',
            engSize,
          )}
        >
          Wings
        </span>
      </span>
    </div>
  )
}
