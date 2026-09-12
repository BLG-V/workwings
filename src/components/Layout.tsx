import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { AppSidebar } from './AppSidebar'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { applyThemePalette, getStoredPalette } from '@/lib/theme'

export function Layout() {
  useEffect(() => {
    applyThemePalette(getStoredPalette())
  }, [])

  return (
    <SidebarProvider>
      <div className="tech-ambient" aria-hidden>
        <div className="tech-aurora" />
        <span className="tech-blob tech-blob-a" />
        <span className="tech-blob tech-blob-b" />
        <span className="tech-blob tech-blob-c" />
        <span className="tech-blob tech-blob-d" />
      </div>
      <AppSidebar />
      <SidebarInset className="pixel-inset relative z-[1] bg-transparent">
        <main className="pixel-main flex-1 overflow-auto min-h-svh bg-transparent">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
