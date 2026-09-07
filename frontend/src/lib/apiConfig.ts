// Central API configuration, driven by the VITE_API_URL environment variable.
//
// - VITE_API_URL unset (default): same-origin requests against "/api/v1".
//   In development the Vite dev proxy (vite.config.ts) forwards /api to the
//   backend; in the Docker deploy nginx.conf does the same.
// - VITE_API_URL set to an absolute URL (e.g. "https://api.example.com/api/v1"):
//   the frontend talks to a separately deployed backend. The backend must then
//   allow the frontend's origin via FRONTEND_URL in its own .env (CORS).
//
// Trailing slashes in VITE_API_URL are tolerated; the normalized value below
// always yields exactly one trailing slash for REST and none for WebSocket.

const RAW_API_URL: string = import.meta.env.VITE_API_URL?.trim() || '/api/v1'
const NORMALIZED_API_URL: string = RAW_API_URL.replace(/\/+$/, '')

/** REST base URL with a trailing slash, e.g. "/api/v1/" or "https://host/api/v1/". */
export const API_BASE_URL: string = `${NORMALIZED_API_URL}/`

/**
 * WebSocket base URL derived from the API URL:
 * absolute "http(s)://..." becomes "ws(s)://...", a relative base is resolved
 * against the current origin (matching same-origin deployments).
 */
export const API_WS_BASE_URL: string = NORMALIZED_API_URL.startsWith('/')
  ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${NORMALIZED_API_URL}`
  : NORMALIZED_API_URL.replace(/^http/, 'ws')
