import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const deepseekKey = env.DEEPSEEK_API_KEY || ''
  const bochaKey = env.BOCHA_API_KEY || ''
  const pollinationsKey =
    env.POLLINATIONS_API_KEY || env.VITE_POLLINATIONS_KEY || ''
  const workwingsTarget =
    env.WORKWINGS_API_TARGET ||
    env.VITE_WORKWINGS_API_TARGET ||
    'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      proxy: {
        // WorkWings FastAPI backend. Production should serve /api/v1 from the same origin.
        '/api/v1': {
          target: workwingsTarget,
          changeOrigin: true,
        },
        '/api/deepseek': {
          target: 'https://api.deepseek.com',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/deepseek/, ''),
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              if (deepseekKey) {
                proxyReq.setHeader('Authorization', `Bearer ${deepseekKey}`)
              }
              // 避免代理缓冲 SSE，保证前端流式到达
              proxyReq.setHeader('Accept', 'text/event-stream')
            })
            proxy.on('proxyRes', (proxyRes) => {
              // 关闭可能的压缩缓冲，便于逐块转发
              if (
                proxyRes.headers['content-type']?.includes('text/event-stream')
              ) {
                proxyRes.headers['cache-control'] = 'no-cache'
                proxyRes.headers['x-accel-buffering'] = 'no'
              }
            })
          },
        },
        '/api/bocha': {
          target: 'https://api.bochaai.com',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/bocha/, ''),
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              if (bochaKey) {
                proxyReq.setHeader('Authorization', `Bearer ${bochaKey}`)
              }
            })
          },
        },
        // 文生图：Pollinations 新统一端点
        '/api/pollinations': {
          target: 'https://gen.pollinations.ai',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/pollinations/, ''),
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              if (pollinationsKey) {
                proxyReq.setHeader(
                  'Authorization',
                  `Bearer ${pollinationsKey}`,
                )
              }
            })
          },
        },
        // MAWP Python 内核（默认 8787）
        '/api/mawp': {
          target: 'http://127.0.0.1:8787',
          changeOrigin: true,
          ws: true,
          rewrite: (p) => p.replace(/^\/api\/mawp/, '/api'),
        },
      },
    },
  }
})
