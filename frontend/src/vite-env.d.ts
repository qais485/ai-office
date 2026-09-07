/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the backend API, e.g. "https://api.example.com/api/v1". Unset = same-origin "/api/v1". */
  readonly VITE_API_URL?: string
  /** Google OAuth client id used on the login page. */
  readonly VITE_GOOGLE_CLIENT_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
