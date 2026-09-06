import { useState, useEffect } from 'react'
import type { Integration, IntegrationAccount } from '../types'
import { officeService } from '../services/office'

const INTEGRATION_ICONS: Record<string, string> = {
  gmail: 'M',
  telegram: 'T',
  instagram: 'I',
  slack: 'S',
  discord: 'D',
  google_calendar: 'C',
  google_drive: 'G',
  notion: 'N',
  crm: 'R',
}

const INTEGRATION_COLORS: Record<string, { bg: string; text: string }> = {
  gmail: { bg: 'bg-red-100', text: 'text-red-700' },
  telegram: { bg: 'bg-blue-100', text: 'text-blue-700' },
  instagram: { bg: 'bg-pink-100', text: 'text-pink-700' },
  slack: { bg: 'bg-purple-100', text: 'text-purple-700' },
  discord: { bg: 'bg-indigo-100', text: 'text-indigo-700' },
  google_calendar: { bg: 'bg-blue-100', text: 'text-blue-700' },
  google_drive: { bg: 'bg-green-100', text: 'text-green-700' },
  notion: { bg: 'bg-gray-100', text: 'text-gray-700' },
  crm: { bg: 'bg-amber-100', text: 'text-amber-700' },
}

function IntegrationCard({
  integration,
  account,
  onConnect,
  onDisconnect,
}: {
  integration: Integration
  account?: IntegrationAccount
  onConnect: (integration: Integration) => void
  onDisconnect: (integration: Integration) => void
}) {
  const colors = INTEGRATION_COLORS[integration.name] || { bg: 'bg-gray-100', text: 'text-gray-700' }
  const iconLetter = INTEGRATION_ICONS[integration.name] || integration.display_name.charAt(0)
  const isConnected = account?.status === 'connected'
  const igUsername =
    integration.name === 'instagram'
      ? ((account?.config?.username as string | undefined) ?? null)
      : null

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${colors.bg}`}>
            <span className={`text-lg font-bold ${colors.text}`}>{iconLetter}</span>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{integration.display_name}</h3>
            <p className="text-xs text-gray-500 capitalize">
              {igUsername ? (
                <span className="font-medium text-pink-700">@{igUsername}</span>
              ) : (
                `${integration.auth_type} auth`
              )}
            </p>
          </div>
        </div>
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          isConnected ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
        }`}>
          {isConnected ? 'Connected' : 'Not connected'}
        </span>
      </div>

      <p className="text-sm text-gray-600 mb-4 line-clamp-2">
        {integration.description || 'No description available'}
      </p>

      {integration.capabilities && (
        <div className="mb-4">
          <p className="text-xs font-medium text-gray-500 mb-2">Capabilities</p>
          <div className="flex flex-wrap gap-1">
            {Object.keys(integration.capabilities).slice(0, 4).map((cap) => (
              <span key={cap} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                {cap.replace(/_/g, ' ')}
              </span>
            ))}
            {Object.keys(integration.capabilities).length > 4 && (
              <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-xs">
                +{Object.keys(integration.capabilities).length - 4} more
              </span>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-gray-100">
        {isConnected ? (
          <>
            <span className="text-xs text-gray-500">
              Last sync: {account?.last_sync_at ? new Date(account.last_sync_at).toLocaleDateString() : 'Never'}
            </span>            <button
              onClick={() => onDisconnect(integration)}
              className="px-3 py-1.5 text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
            >
              Disconnect
            </button>
          </>
        ) : (
          <>
            <span className="text-xs text-gray-500">
              {Object.keys(integration.capabilities || {}).length} capabilities
            </span>
            <button
              onClick={() => onConnect(integration)}
              className="px-3 py-1.5 text-sm font-medium text-primary-600 hover:text-primary-700 hover:bg-primary-50 rounded-lg transition-colors"
            >
              Connect
            </button>
          </>
        )}
      </div>
    </div>
  )
}

function ConnectModal({
  integration,
  onClose,
  onConnect,
  onOAuth,
}: {
  integration: Integration
  onClose: () => void
  onConnect: (credentials: Record<string, unknown>) => void
  onOAuth: () => void
}) {
  const [credentials, setCredentials] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)

  const isOAuth = integration.auth_type === 'oauth2'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (isOAuth) {
      onOAuth()
      return
    }
    if (!credentials.api_key && !credentials.bot_token) {
      return
    }
    setLoading(true)
    try {
      await onConnect(credentials)
      onClose()
    } catch {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Connect {integration.display_name}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          {isOAuth
            ? `Authorize ${integration.display_name} to connect your account.`
            : `Enter your ${integration.display_name} credentials to connect.`}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isOAuth && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
                <input
                  type="password"
                  value={credentials.api_key || ''}
                  onChange={(e) => setCredentials({ ...credentials, api_key: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="Enter your API key"
                  required
                />
              </div>
              {integration.auth_type === 'bot_token' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Bot Token</label>
                  <input
                    type="password"
                    value={credentials.bot_token || ''}
                    onChange={(e) => setCredentials({ ...credentials, bot_token: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="Enter your bot token"
                    required
                  />
                </div>
              )}
            </>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? 'Connecting...' : isOAuth ? 'Authorize' : 'Connect'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [accounts, setAccounts] = useState<IntegrationAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [connectModal, setConnectModal] = useState<Integration | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [integrationsRes, accountsRes] = await Promise.all([
        officeService.getIntegrations(),
        officeService.getIntegrationAccounts(),
      ])
      setIntegrations(integrationsRes.data ?? [])
      setAccounts(accountsRes.data ?? [])
    } catch (err) {
      setError('Failed to load integrations')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleConnect = async (integration: Integration) => {
    setConnectModal(integration)
  }

  const handleDisconnect = async (integration: Integration) => {
    if (!confirm(`Disconnect ${integration.display_name}?`)) return

    try {
      await officeService.disconnectIntegration(integration.id)
      await loadData()
    } catch (err) {
      console.error('Failed to disconnect:', err)
    }
  }

  const handleConnectSubmit = async (credentials: Record<string, unknown>) => {
    if (!connectModal) return
    await officeService.connectIntegration(connectModal.id, credentials)
    await loadData()
  }

  const handleOAuth = async () => {
    if (!connectModal) return
    setConnectModal(null)
    try {
      const result = await officeService.getOAuth2AuthorizeUrl(connectModal.id)
      if (result.success && result.data) {
        window.location.href = result.data.authorization_url
      } else {
        alert(`Failed to start OAuth2 flow: ${result.error || 'Unknown error'}`)
      }
    } catch {
      alert('Failed to start OAuth2 flow. Please try again.')
    }
  }

  const getAccountForIntegration = (integrationId: string) =>
    accounts.find((a) => a.integration_id === integrationId)

  const connectedCount = accounts.filter((a) => a.status === 'connected').length

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Loading integrations...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-red-600 mb-2">{error}</p>
          <button onClick={loadData} className="text-sm text-primary-600 hover:text-primary-700">
            Try again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Integration Center</h1>
            <p className="text-gray-500 mt-1">Connect and manage your integrations</p>
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>{integrations.length} available</span>
            <span className="w-1 h-1 bg-gray-300 rounded-full" />
            <span>{connectedCount} connected</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {integrations.map((integration) => (
          <IntegrationCard
            key={integration.id}
            integration={integration}
            account={getAccountForIntegration(integration.id)}
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
          />
        ))}
      </div>

      {connectModal && (
        <ConnectModal
          integration={connectModal}
          onClose={() => setConnectModal(null)}
          onConnect={handleConnectSubmit}
          onOAuth={handleOAuth}
        />
      )}
    </div>
  )
}
