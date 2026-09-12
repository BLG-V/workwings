export type ThemePalette =
  | 'harbor'
  | 'moss'
  | 'dusk'
  | 'clay'
  | 'cloud'
  | 'ink'
  /** @deprecated 兼容旧存储 */
  | 'ion'
  | 'matrix'
  | 'plasma'
  | 'solar'
  | 'arctic'
  | 'chrome'
  | 'orbit'
  | 'frost'
  | 'aurora'
  | 'ember'
  | 'graphite'
  | 'mist'
  | 'standard'
  | 'cyber'
  | 'circuit'
  | 'quantum'
  | 'neon'

export interface ThemePreset {
  id: Exclude<
    ThemePalette,
    | 'ion'
    | 'matrix'
    | 'plasma'
    | 'solar'
    | 'arctic'
    | 'chrome'
    | 'orbit'
    | 'frost'
    | 'aurora'
    | 'ember'
    | 'graphite'
    | 'mist'
    | 'standard'
    | 'cyber'
    | 'circuit'
    | 'quantum'
    | 'neon'
  >
  label: string
  desc: string
  hue: string
  swatch: string[]
  vars: Record<string, string>
  scheme: 'dark' | 'light'
}

const LEGACY_MAP: Record<string, ThemePreset['id']> = {
  standard: 'cloud',
  cyber: 'harbor',
  circuit: 'clay',
  quantum: 'ink',
  neon: 'dusk',
  orbit: 'harbor',
  frost: 'cloud',
  aurora: 'moss',
  ember: 'clay',
  graphite: 'ink',
  mist: 'dusk',
  ion: 'harbor',
  matrix: 'moss',
  plasma: 'dusk',
  solar: 'clay',
  arctic: 'cloud',
  chrome: 'ink',
}

type PixelThemeSeed = {
  id: ThemePreset['id']
  label: string
  hue: string
  desc: string
  swatch: string[]
  background: string
  foreground: string
  card: string
  primary: string
  primaryForeground: string
  secondary: string
  secondaryForeground: string
  muted: string
  mutedForeground: string
  accent: string
  accentForeground: string
  border: string
  intel: string
  hot: string
}

function createPixelTheme(seed: PixelThemeSeed): ThemePreset {
  const {
    id,
    label,
    hue,
    desc,
    swatch,
    background,
    foreground,
    card,
    primary,
    primaryForeground,
    secondary,
    secondaryForeground,
    muted,
    mutedForeground,
    accent,
    accentForeground,
    border,
    intel,
    hot,
  } = seed
  return {
    id,
    label,
    hue,
    desc,
    swatch,
    scheme: 'dark',
    vars: {
      '--background': background,
      '--foreground': foreground,
      '--card': card,
      '--card-foreground': foreground,
      '--popover': card,
      '--popover-foreground': foreground,
      '--primary': primary,
      '--primary-foreground': primaryForeground,
      '--secondary': secondary,
      '--secondary-foreground': secondaryForeground,
      '--muted': muted,
      '--muted-foreground': mutedForeground,
      '--accent': accent,
      '--accent-foreground': accentForeground,
      '--border': border,
      '--input': border,
      '--ring': primary,
      '--sidebar-background': background,
      '--sidebar-foreground': foreground,
      '--sidebar-primary': primary,
      '--sidebar-primary-foreground': primaryForeground,
      '--sidebar-accent': secondary,
      '--sidebar-accent-foreground': secondaryForeground,
      '--sidebar-border': border,
      '--sidebar-ring': primary,
      '--intel': intel,
      '--destructive': '0 82% 66%',
      '--destructive-foreground': '228 20% 7%',
      '--chat-user': secondary,
      '--chat-user-fg': foreground,
      '--chat-assistant': card,
      '--composer': background,
      '--trace-a': primary,
      '--trace-b': intel,
      '--blob-1': `${primary} / 0`,
      '--blob-2': `${intel} / 0`,
      '--blob-3': `${primary} / 0`,
      '--auto': intel,
      '--needs': primary,
      '--warn': '43 100% 62%',
      '--down': '0 82% 66%',
      '--success': '142 70% 56%',
      '--pixel-shadow': `${primary} / 0.86`,
      '--pixel-bg': `hsl(${background})`,
      '--pixel-surface': `hsl(${card})`,
      '--pixel-surface-2': `hsl(${muted})`,
      '--pixel-accent': `hsl(${primary})`,
      '--pixel-secondary': intel,
      '--pixel-hot': hot,
      '--pixel-grid': `hsl(${border})`,
      '--pixel-ink': `hsl(${foreground})`,
    },
  }
}

/** 六套深色像素主题：每套代表一种终端现场，而不是只替换一个强调色。 */
export const THEME_PRESETS: ThemePreset[] = [
  createPixelTheme({
    id: 'harbor',
    label: '酸黄指挥台',
    hue: '荧光柠檬',
    desc: '黑色控制室、荧光主控块、蓝色错位信号',
    swatch: ['#07090d', '#10151c', '#c7ff00', '#3347ff'],
    background: '228 20% 5%',
    foreground: '48 30% 96%',
    card: '228 18% 8%',
    primary: '74 100% 50%',
    primaryForeground: '228 25% 6%',
    secondary: '228 16% 12%',
    secondaryForeground: '48 18% 90%',
    muted: '228 14% 11%',
    mutedForeground: '220 8% 62%',
    accent: '74 60% 18%',
    accentForeground: '74 100% 72%',
    border: '228 12% 22%',
    intel: '232 100% 60%',
    hot: '330 100% 59%',
  }),
  createPixelTheme({
    id: 'moss',
    label: '绿码中继',
    hue: '像素绿',
    desc: '老式终端绿字、深墨表面、青色数据跳线',
    swatch: ['#06100d', '#0d1a15', '#8cff66', '#28d7b2'],
    background: '158 30% 4%',
    foreground: '116 50% 94%',
    card: '158 26% 7%',
    primary: '108 100% 70%',
    primaryForeground: '158 35% 5%',
    secondary: '158 22% 11%',
    secondaryForeground: '122 30% 88%',
    muted: '158 20% 10%',
    mutedForeground: '154 14% 58%',
    accent: '158 65% 16%',
    accentForeground: '135 100% 78%',
    border: '158 18% 23%',
    intel: '164 72% 53%',
    hot: '72 100% 61%',
  }),
  createPixelTheme({
    id: 'dusk',
    label: '品红编排间',
    hue: '品红蓝',
    desc: '品红主控、蓝色轨道、适合密集工作流编排',
    swatch: ['#110816', '#21102a', '#ff3fa4', '#5b5cff'],
    background: '286 35% 5%',
    foreground: '330 35% 96%',
    card: '286 30% 9%',
    primary: '326 100% 62%',
    primaryForeground: '286 36% 7%',
    secondary: '258 35% 18%',
    secondaryForeground: '315 25% 91%',
    muted: '286 26% 12%',
    mutedForeground: '286 12% 65%',
    accent: '326 58% 19%',
    accentForeground: '326 100% 78%',
    border: '286 20% 25%',
    intel: '238 100% 68%',
    hot: '45 100% 61%',
  }),
  createPixelTheme({
    id: 'clay',
    label: '琥珀审批台',
    hue: '警示琥珀',
    desc: '煤灰工作台、琥珀指令、红色风险贴签',
    swatch: ['#100d08', '#21170b', '#ffbd4a', '#ff5d55'],
    background: '32 28% 5%',
    foreground: '43 42% 95%',
    card: '32 25% 8%',
    primary: '40 100% 65%',
    primaryForeground: '30 35% 8%',
    secondary: '28 28% 14%',
    secondaryForeground: '40 30% 90%',
    muted: '32 24% 11%',
    mutedForeground: '35 15% 63%',
    accent: '39 64% 19%',
    accentForeground: '43 100% 78%',
    border: '32 19% 25%',
    intel: '16 100% 67%',
    hot: '3 100% 67%',
  }),
  createPixelTheme({
    id: 'cloud',
    label: '薄荷值守台',
    hue: '电光青',
    desc: '冷黑底、薄荷主控、蓝色长时值守信号',
    swatch: ['#061014', '#0c2024', '#54f5cf', '#4cb8ff'],
    background: '194 35% 5%',
    foreground: '168 35% 95%',
    card: '194 30% 8%',
    primary: '166 88% 64%',
    primaryForeground: '193 35% 7%',
    secondary: '194 28% 13%',
    secondaryForeground: '170 28% 89%',
    muted: '194 24% 11%',
    mutedForeground: '190 15% 62%',
    accent: '166 60% 18%',
    accentForeground: '166 100% 78%',
    border: '194 20% 24%',
    intel: '202 100% 68%',
    hot: '78 100% 62%',
  }),
  createPixelTheme({
    id: 'ink',
    label: '黑白审计台',
    hue: '单色灰阶',
    desc: '单色审计现场、低干扰、突出日志与证据',
    swatch: ['#090a0c', '#17191e', '#f3f4f6', '#8b93a0'],
    background: '220 10% 5%',
    foreground: '220 12% 94%',
    card: '220 8% 9%',
    primary: '220 12% 88%',
    primaryForeground: '220 12% 8%',
    secondary: '220 8% 15%',
    secondaryForeground: '220 10% 88%',
    muted: '220 7% 12%',
    mutedForeground: '220 5% 62%',
    accent: '220 8% 22%',
    accentForeground: '220 12% 96%',
    border: '220 7% 26%',
    intel: '220 12% 68%',
    hot: '220 15% 96%',
  }),
]

const STORAGE_KEY = 'mawp-theme-palette-v2'
const DEFAULT_PALETTE: ThemePreset['id'] = 'harbor'

export function resolvePaletteId(raw: string | null | undefined): ThemePreset['id'] {
  if (!raw) return DEFAULT_PALETTE
  if (LEGACY_MAP[raw]) return LEGACY_MAP[raw]
  if (THEME_PRESETS.some((p) => p.id === raw)) return raw as ThemePreset['id']
  return DEFAULT_PALETTE
}

export function getStoredPalette(): ThemePreset['id'] {
  try {
    return resolvePaletteId(localStorage.getItem(STORAGE_KEY))
  } catch {
    return DEFAULT_PALETTE
  }
}

function buildBodyGlow(): string {
  return 'hsl(var(--background))'
}

export function applyThemePalette(id: ThemePalette | string) {
  const resolved = resolvePaletteId(id)
  const preset = THEME_PRESETS.find((p) => p.id === resolved) ?? THEME_PRESETS[0]
  const root = document.documentElement
  Object.entries(preset.vars).forEach(([k, v]) => root.style.setProperty(k, v))
  root.setAttribute('data-palette', preset.id)
  root.setAttribute('data-scheme', preset.scheme)
  root.style.colorScheme = preset.scheme
  root.setAttribute('data-theme-style', 'pixel')
  document.body.style.backgroundImage = buildBodyGlow()
  document.body.style.backgroundColor = 'hsl(var(--background))'
  document.body.style.backgroundSize = 'auto'
  document.body.style.backgroundAttachment = 'fixed'
  try {
    localStorage.setItem(STORAGE_KEY, preset.id)
  } catch {
    /* ignore */
  }
}
