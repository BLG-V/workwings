import { useEffect, useState } from 'react'
import {
  THEME_PRESETS,
  applyThemePalette,
  getStoredPalette,
  type ThemePreset,
} from '@/lib/theme'

export type ThemePaletteId = ThemePreset['id']

export function useThemePalette() {
  const [palette, setPalette] = useState<ThemePaletteId>(() => {
    if (typeof window === 'undefined') return 'cloud'
    return getStoredPalette()
  })

  useEffect(() => {
    applyThemePalette(palette)
  }, [palette])

  return {
    palette,
    setPalette: (id: ThemePaletteId) => setPalette(id),
    presets: THEME_PRESETS,
  }
}
