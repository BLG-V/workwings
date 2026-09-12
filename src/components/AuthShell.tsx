import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import BrandLogo from '@/components/BrandLogo'

export default function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <div className="relative min-h-svh overflow-hidden">
      <div className="tech-ambient" aria-hidden>
        <div className="tech-aurora" />
        <span className="tech-blob tech-blob-a" />
        <span className="tech-blob tech-blob-b" />
        <span className="tech-blob tech-blob-c" />
        <span className="tech-blob tech-blob-d" />
      </div>
      <div className="relative z-10 mx-auto grid min-h-svh w-full max-w-7xl items-center gap-10 px-6 py-10 lg:grid-cols-[1.25fr_0.85fr] lg:gap-16 lg:px-10 lg:py-16">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="max-w-2xl"
        >
          <BrandLogo size={104} className="mb-9 overflow-visible" />
          <p className="text-2xl md:text-3xl lg:text-[2.15rem] lg:leading-snug text-foreground font-display font-semibold tracking-tight">
            {title}
          </p>
          <p className="mt-4 max-w-xl text-base md:text-lg leading-relaxed text-muted-foreground">
            {subtitle}
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.06 }}
          className="w-full max-w-md justify-self-center lg:justify-self-end"
        >
          {children}
        </motion.div>
      </div>
    </div>
  )
}
