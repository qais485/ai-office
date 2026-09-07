import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
//
// All API-related settings are environment-driven (see .env.example):
//   VITE_API_URL          — backend API base URL used by the app at runtime.
//                           Unset = same-origin mode ("/api/v1"), where API and
//                           WebSocket requests hit this dev server and are proxied.
//   VITE_API_PROXY_TARGET — origin of the backend for the same-origin dev proxy,
//                           e.g. http://localhost:8000. Falls back to the origin of
//                           VITE_API_URL when it is an absolute URL. No URL is
//                           hardcoded here: without one of the two variables the
//                           proxy is simply not configured.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  const apiUrl = env.VITE_API_URL?.trim()
  const proxyTarget =
    env.VITE_API_PROXY_TARGET?.trim() ||
    (apiUrl && /^https?:\/\//i.test(apiUrl) ? new URL(apiUrl).origin : undefined)

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': '/src',
      },
    },
    server: {
      port: 5173,
      ...(proxyTarget
        ? {
            proxy: {
              // Covers REST (/api/...) and WebSocket upgrades (/api/v1/ws/...).
              '/api': {
                target: proxyTarget,
                changeOrigin: true,
                ws: true,
              },
            },
          }
        : {}),
    },
  }
})
