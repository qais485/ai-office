import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/useAuthStore'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string
            callback: (response: { credential: string }) => void
          }) => void
          renderButton: (element: HTMLElement, config: Record<string, unknown>) => void
        }
      }
    }
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''

const LoginPage = () => {
  const buttonRef = useRef<HTMLDivElement>(null)
  const { googleLogin, isAuthenticated, isLoading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true })
    }
  }, [isAuthenticated, navigate])

  useEffect(() => {
    if (!window.google || !GOOGLE_CLIENT_ID) return

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async (response) => {
        const success = await googleLogin(response.credential)
        if (success) {
          navigate('/dashboard')
        }
      },
    })

    if (buttonRef.current) {
      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: 'outline',
        size: 'large',
        width: 320,
        text: 'signin_with',
      })
    }
  }, [googleLogin, navigate])

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 bg-[#06060f]">
      <div className="w-full max-w-md">
        <div className="bg-white/[0.03] rounded-xl border border-white/10 p-8">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-white">Sign in</h1>
            <p className="mt-2 text-sm text-white/70">
              Welcome back to AI Virtual Office
            </p>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/25 text-red-400 text-sm rounded-lg px-4 py-3 mb-6">
              {error}
              <button
                type="button"
                onClick={clearError}
                className="ml-2 text-red-400 hover:text-red-300 underline"
              >
                Dismiss
              </button>
            </div>
          )}

          {isLoading && (
            <div className="flex justify-center mb-6">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-400" />
            </div>
          )}

          {!GOOGLE_CLIENT_ID && (
            <div className="bg-yellow-500/10 border border-yellow-500/25 text-yellow-400 text-sm rounded-lg px-4 py-3 mb-6">
              Google Client ID is not configured. Set <code>VITE_GOOGLE_CLIENT_ID</code> in your <code>.env</code> file.
            </div>
          )}

          <div className="flex justify-center">
            <div ref={buttonRef} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
