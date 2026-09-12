import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Check } from 'lucide-react'
import { Toaster } from 'sonner'
import './index.css'
import App from './app.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
      <Toaster
        theme="light"
        position="top-right"
        icons={{
          success: (
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-neutral-900 text-white">
              <Check className="size-3" strokeWidth={3} />
            </span>
          ),
        }}
        toastOptions={{
          className:
            '!rounded-none !border !border-border !bg-card !text-foreground !shadow-[4px_4px_0_hsl(var(--primary)/0.24)]',
          classNames: {
            success: '!bg-card !text-foreground',
            title: '!text-[14px] !font-medium !text-foreground',
            description: '!text-muted-foreground',
          },
        }}
      />
    </BrowserRouter>
  </StrictMode>,
)
