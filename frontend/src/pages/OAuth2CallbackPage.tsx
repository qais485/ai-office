import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'

export default function OAuth2CallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    const result = searchParams.get('status')
    const errorMsg = searchParams.get('message')
    const accountId = searchParams.get('account_id')
    const username = searchParams.get('username')

    if (result === 'success') {
      setStatus('success')
      setMessage(
        username
          ? `Instagram @${username} connected successfully!`
          : accountId
            ? 'Integration connected successfully!'
            : 'Integration connected!'
      )
    } else if (result === 'error') {
      setStatus('error')
      setMessage(errorMsg || 'Failed to connect integration. Please try again.')
    } else {
      setStatus('error')
      setMessage('Invalid callback parameters.')
    }
  }, [searchParams])

  const handleContinue = () => {
    navigate('/integrations')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#06060f]">
      <div className="max-w-md w-full bg-[#0d0d1a] rounded-xl border border-white/10 shadow-2xl shadow-black/60 p-8 text-center">
        {status === 'loading' && (
          <>
            <div className="w-12 h-12 border-4 border-white/10 border-t-indigo-400 rounded-full animate-spin mx-auto mb-4" />
            <h1 className="text-xl font-semibold text-white mb-2">Processing...</h1>
            <p className="text-white/50">Completing your integration connection.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="w-16 h-16 bg-green-500/15 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-white mb-2">Connected!</h1>
            <p className="text-white/50 mb-6">{message}</p>
            <button
              onClick={handleContinue}
              className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-colors"
            >
              Back to Integrations
            </button>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="w-16 h-16 bg-red-500/15 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-white mb-2">Connection Failed</h1>
            <p className="text-white/50 mb-6">{message}</p>
            <button
              onClick={handleContinue}
              className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-colors"
            >
              Back to Integrations
            </button>
          </>
        )}
      </div>
    </div>
  )
}
