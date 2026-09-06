import { useState, useEffect, useCallback } from 'react'
import type { EmailAccount, CreateEmailAccountRequest } from '../types'
import { officeService } from '../services/office'
import { useAuthStore } from '../stores/useAuthStore'

function EmailAccountsPage() {
  const user = useAuthStore((s) => s.user)
  const [accounts, setAccounts] = useState<EmailAccount[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingAccount, setEditingAccount] = useState<EmailAccount | null>(null)
  const [deletingAccount, setDeletingAccount] = useState<EmailAccount | null>(null)
  const [syncingId, setSyncingId] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    if (!user) return
    setIsLoading(true)
    setError(null)
    const result = await officeService.getEmailAccounts(user.id)
    if (result.success && result.data) {
      setAccounts(result.data)
    } else {
      setError(result.error ?? 'Failed to load email accounts')
    }
    setIsLoading(false)
  }, [user])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleCreate = async (data: CreateEmailAccountRequest) => {
    if (!user) return
    const result = await officeService.createEmailAccount(user.id, data)
    if (!result.success) throw new Error(result.error ?? 'Failed to create account')
    await fetchData()
  }

  const handleUpdate = async (id: string, data: Partial<CreateEmailAccountRequest>) => {
    const result = await officeService.updateEmailAccount(id, data)
    if (!result.success) throw new Error(result.error ?? 'Failed to update account')
    await fetchData()
  }

  const handleDelete = async (id: string) => {
    try {
      await officeService.deleteEmailAccount(id)
      setDeletingAccount(null)
      await fetchData()
    } catch {
      // Error shown via service toast
    }
  }

  const handleSync = async (id: string) => {
    setSyncingId(id)
    try {
      await officeService.syncEmailAccount(id)
      await fetchData()
    } finally {
      setSyncingId(null)
    }
  }

  const handleToggleActive = async (account: EmailAccount) => {
    try {
      await handleUpdate(account.id, { is_active: !account.is_active } as any)
    } catch {
      // Error shown via handleUpdate
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-64 bg-gray-200 rounded animate-pulse mt-2" />
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-200 rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">{error}</div>
        <button type="button" onClick={fetchData} className="px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-medium hover:bg-primary-700 transition-colors">
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Email Accounts</h1>
          <p className="mt-1 text-sm text-gray-500">Connect and manage email accounts for the AI Support Agent.</p>
        </div>
        <button type="button" onClick={() => setShowCreateModal(true)} className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Connect Account
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
          </svg>
          <h3 className="mt-3 text-sm font-medium text-gray-900">No email accounts</h3>
          <p className="mt-1 text-sm text-gray-500">Connect an email account to start receiving and processing emails.</p>
          <button type="button" onClick={() => setShowCreateModal(true)} className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            Connect Account
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {accounts.map((account) => (
            <div key={account.id} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4">
              <span className="flex items-center justify-center h-10 w-10 rounded-full bg-primary-100 text-primary-700 text-sm font-medium shrink-0">
                {account.email_address.charAt(0).toUpperCase()}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-gray-900 truncate">{account.email_address}</p>
                  {account.display_name && (
                    <span className="text-xs text-gray-400">({account.display_name})</span>
                  )}
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${account.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${account.is_active ? 'bg-green-500' : 'bg-gray-400'}`} />
                    {account.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                  <span>IMAP: {account.imap_host}:{account.imap_port}</span>
                  <span>SMTP: {account.smtp_host}:{account.smtp_port}</span>
                  {account.last_sync_at && (
                    <span>Last sync: {new Date(account.last_sync_at).toLocaleString()}</span>
                  )}
                  {account.sync_error && (
                    <span className="text-red-500 truncate max-w-[200px]">{account.sync_error}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button type="button" onClick={() => handleSync(account.id)} disabled={syncingId === account.id} className="p-1.5 rounded-md text-gray-400 hover:text-primary-600 hover:bg-primary-50 transition-colors disabled:opacity-50" title="Sync now">
                  <svg className={`h-4 w-4 ${syncingId === account.id ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                  </svg>
                </button>
                <button type="button" onClick={() => handleToggleActive(account)} className={`p-1.5 rounded-md transition-colors ${account.is_active ? 'text-green-500 hover:text-gray-500 hover:bg-gray-100' : 'text-gray-400 hover:text-green-600 hover:bg-green-50'}`} title={account.is_active ? 'Deactivate' : 'Activate'}>
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </button>
                <button type="button" onClick={() => setEditingAccount(account)} className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors" title="Edit">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
                  </svg>
                </button>
                <button type="button" onClick={() => setDeletingAccount(account)} className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors" title="Delete">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreateModal && (
        <AccountFormModal title="Connect Email Account" onClose={() => setShowCreateModal(false)} onSubmit={handleCreate} />
      )}

      {editingAccount && (
        <AccountFormModal title="Edit Email Account" account={editingAccount} onClose={() => setEditingAccount(null)} onSubmit={(data) => handleUpdate(editingAccount.id, data)} />
      )}

      {deletingAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDeletingAccount(null)} />
          <div className="relative bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 overflow-hidden">
            <div className="px-5 py-4">
              <h2 className="text-base font-semibold text-gray-900">Delete Account</h2>
              <p className="mt-2 text-sm text-gray-600">Are you sure you want to delete {deletingAccount.email_address}? This cannot be undone.</p>
            </div>
            <div className="px-5 py-3 bg-gray-50 flex justify-end gap-2">
              <button type="button" onClick={() => setDeletingAccount(null)} className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Cancel</button>
              <button type="button" onClick={() => handleDelete(deletingAccount.id)} className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function AccountFormModal({ title, account, onClose, onSubmit }: {
  title: string
  account?: EmailAccount
  onClose: () => void
  onSubmit: (data: CreateEmailAccountRequest) => Promise<void>
}) {
  const [emailAddress, setEmailAddress] = useState(account?.email_address ?? '')
  const [displayName, setDisplayName] = useState(account?.display_name ?? '')
  const [imapHost, setImapHost] = useState(account?.imap_host ?? '')
  const [imapPort, setImapPort] = useState(account?.imap_port?.toString() ?? '993')
  const [imapUsername, setImapUsername] = useState(account?.imap_username ?? '')
  const [imapPassword, setImapPassword] = useState('')
  const [imapUseSsl, setImapUseSsl] = useState(account?.imap_use_ssl ?? true)
  const [smtpHost, setSmtpHost] = useState(account?.smtp_host ?? '')
  const [smtpPort, setSmtpPort] = useState(account?.smtp_port?.toString() ?? '587')
  const [smtpUsername, setSmtpUsername] = useState(account?.smtp_username ?? '')
  const [smtpPassword, setSmtpPassword] = useState('')
  const [smtpUseSsl, setSmtpUseSsl] = useState(account?.smtp_use_ssl ?? true)
  const [syncFrequency, setSyncFrequency] = useState(account?.sync_frequency_minutes?.toString() ?? '5')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ type: string; success: boolean; message: string } | null>(null)
  const [testing, setTesting] = useState<string | null>(null)

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  const buildData = (): CreateEmailAccountRequest => ({
    email_address: emailAddress.trim(),
    display_name: displayName.trim() || undefined,
    imap_host: imapHost.trim(),
    imap_port: parseInt(imapPort) || 993,
    imap_username: imapUsername.trim(),
    imap_password: imapPassword || '',
    imap_use_ssl: imapUseSsl,
    smtp_host: smtpHost.trim(),
    smtp_port: parseInt(smtpPort) || 587,
    smtp_username: smtpUsername.trim(),
    smtp_password: smtpPassword || '',
    smtp_use_ssl: smtpUseSsl,
    sync_frequency_minutes: parseInt(syncFrequency) || 5,
  })

  const handleTest = async (type: 'imap' | 'smtp') => {
    setTesting(type)
    setTestResult(null)
    const data = buildData()
    const result = type === 'imap'
      ? await officeService.testImapConnection(data)
      : await officeService.testSmtpConnection(data)
    const success = result.success && (result.data?.success ?? false)
    setTestResult({ type, success, message: result.data?.message ?? result.error ?? 'Test failed' })
    setTesting(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!emailAddress.trim() || !imapHost.trim() || !imapUsername.trim() || !smtpHost.trim() || !smtpUsername.trim()) {
      setFormError('Email, IMAP, and SMTP fields are required')
      return
    }
    if (!account && !imapPassword.trim()) {
      setFormError('IMAP password is required')
      return
    }
    setIsSubmitting(true)
    setFormError(null)
    try {
      await onSubmit(buildData())
      onClose()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save account')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden max-h-[85vh] flex flex-col">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between shrink-0">
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          <button type="button" onClick={onClose} className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4 overflow-y-auto flex-1">
          {formError && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">{formError}</div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email Address <span className="text-red-500">*</span></label>
              <input type="email" value={emailAddress} onChange={(e) => setEmailAddress(e.target.value)} placeholder="support@company.com" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
              <input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Support Team" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
            </div>
          </div>

          <div className="border-t border-gray-200 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-900">IMAP Settings (Incoming)</h3>
              <button type="button" onClick={() => handleTest('imap')} disabled={testing === 'imap'} className="text-xs font-medium text-primary-600 hover:text-primary-700 disabled:opacity-50">
                {testing === 'imap' ? 'Testing...' : 'Test Connection'}
              </button>
            </div>
            {testResult?.type === 'imap' && (
              <div className={`text-xs rounded-lg px-3 py-2 mb-3 ${testResult.success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>{testResult.message}</div>
            )}
            <div className="grid grid-cols-4 gap-3">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">Host <span className="text-red-500">*</span></label>
                <input type="text" value={imapHost} onChange={(e) => setImapHost(e.target.value)} placeholder="imap.gmail.com" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Port</label>
                <input type="number" value={imapPort} onChange={(e) => setImapPort(e.target.value)} className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
              </div>
              <div className="flex items-end pb-1">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={imapUseSsl} onChange={(e) => setImapUseSsl(e.target.checked)} className="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                  SSL
                </label>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Username <span className="text-red-500">*</span></label>
                <input type="text" value={imapUsername} onChange={(e) => setImapUsername(e.target.value)} placeholder="user@gmail.com" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Password <span className="text-red-500">*</span></label>
                <input type="password" value={imapPassword} onChange={(e) => setImapPassword(e.target.value)} placeholder={account ? '(unchanged)' : 'App password'} className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
              </div>
            </div>
          </div>

          <div className="border-t border-gray-200 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-900">SMTP Settings (Outgoing)</h3>
              <button type="button" onClick={() => handleTest('smtp')} disabled={testing === 'smtp'} className="text-xs font-medium text-primary-600 hover:text-primary-700 disabled:opacity-50">
                {testing === 'smtp' ? 'Testing...' : 'Test Connection'}
              </button>
            </div>
            {testResult?.type === 'smtp' && (
              <div className={`text-xs rounded-lg px-3 py-2 mb-3 ${testResult.success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>{testResult.message}</div>
            )}
            <div className="grid grid-cols-4 gap-3">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">Host <span className="text-red-500">*</span></label>
                <input type="text" value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} placeholder="smtp.gmail.com" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Port</label>
                <input type="number" value={smtpPort} onChange={(e) => setSmtpPort(e.target.value)} className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
              </div>
              <div className="flex items-end pb-1">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={smtpUseSsl} onChange={(e) => setSmtpUseSsl(e.target.checked)} className="rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
                  SSL
                </label>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Username <span className="text-red-500">*</span></label>
                <input type="text" value={smtpUsername} onChange={(e) => setSmtpUsername(e.target.value)} placeholder="user@gmail.com" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Password <span className="text-red-500">*</span></label>
                <input type="password" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} placeholder={account ? '(unchanged)' : 'App password'} className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
              </div>
            </div>
          </div>

          <div className="border-t border-gray-200 pt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">Sync Frequency (minutes)</label>
            <input type="number" value={syncFrequency} onChange={(e) => setSyncFrequency(e.target.value)} min="1" max="60" className="w-24 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} disabled={isSubmitting} className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors">Cancel</button>
            <button type="submit" disabled={isSubmitting} className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors">
              {isSubmitting ? 'Saving...' : account ? 'Update Account' : 'Connect Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default EmailAccountsPage
