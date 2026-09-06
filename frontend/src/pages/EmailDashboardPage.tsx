import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import type { EmailMessage, EmailStats, CreateEmailRequest, AgentActivity, EmailAccount } from '../types'
import { officeService } from '../services/office'
import { useAuthStore } from '../stores/useAuthStore'

const EMAIL_STATUS_COLORS: Record<string, string> = {
  new: 'bg-blue-100 text-blue-700',
  processing: 'bg-amber-100 text-amber-700',
  replied: 'bg-green-100 text-green-700',
  escalated: 'bg-red-100 text-red-700',
  failed: 'bg-gray-100 text-gray-500',
}

const EMAIL_STATUS_DOT: Record<string, string> = {
  new: 'bg-blue-500',
  processing: 'bg-amber-500',
  replied: 'bg-green-500',
  escalated: 'bg-red-500',
  failed: 'bg-gray-400',
}

const CATEGORY_COLORS: Record<string, string> = {
  support: 'bg-blue-50 text-blue-600',
  billing: 'bg-amber-50 text-amber-600',
  technical: 'bg-purple-50 text-purple-600',
  general: 'bg-gray-50 text-gray-600',
  spam: 'bg-red-50 text-red-600',
}

function StatCard({ label, value, icon, color }: {
  label: string
  value: number
  icon: React.ReactNode
  color: 'blue' | 'amber' | 'green' | 'red' | 'gray'
}) {
  const bgColors = {
    blue: 'bg-blue-50',
    amber: 'bg-amber-50',
    green: 'bg-green-50',
    red: 'bg-red-50',
    gray: 'bg-gray-50',
  }
  const iconColors = {
    blue: 'text-blue-600',
    amber: 'text-amber-600',
    green: 'text-green-600',
    red: 'text-red-600',
    gray: 'text-gray-500',
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</h3>
        <span className={`p-1.5 rounded-lg ${bgColors[color]}`}>
          <span className={iconColors[color]}>{icon}</span>
        </span>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  )
}

function EmailDashboardPage() {
  const user = useAuthStore((s) => s.user)
  const [emails, setEmails] = useState<EmailMessage[]>([])
  const [stats, setStats] = useState<EmailStats | null>(null)
  const [activities, setActivities] = useState<AgentActivity[]>([])
  const [accounts, setAccounts] = useState<EmailAccount[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedEmail, setSelectedEmail] = useState<EmailMessage | null>(null)
  const [processingId, setProcessingId] = useState<string | null>(null)
  const [syncingAccountId, setSyncingAccountId] = useState<string | null>(null)
  const [categoryFilter, setCategoryFilter] = useState<string>('all')

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    const [emailsResult, statsResult, activityResult, accountsResult] = await Promise.all([
      officeService.getEmails(),
      officeService.getEmailStats(),
      officeService.getAllActivity(20),
      user ? officeService.getEmailAccounts(user.id) : Promise.resolve({ success: true, data: [] }),
    ])
    if (emailsResult.success && emailsResult.data) setEmails(emailsResult.data)
    if (statsResult.success && statsResult.data) setStats(statsResult.data)
    if (activityResult.success && activityResult.data) setActivities(activityResult.data)
    if (accountsResult.success && accountsResult.data) setAccounts(accountsResult.data)
    if (!emailsResult.success) setError(emailsResult.error ?? 'Failed to load emails')
    setIsLoading(false)
  }, [user])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleCreate = async (data: CreateEmailRequest) => {
    const result = await officeService.createEmail(data)
    if (!result.success) throw new Error(result.error ?? 'Failed to create email')
    await fetchData()
  }

  const handleProcess = async (emailId: string) => {
    setProcessingId(emailId)
    try {
      const result = await officeService.processEmail(emailId)
      if (result.success && result.data) {
        setEmails((prev) => prev.map((e) => (e.id === emailId ? result.data! : e)))
        if (selectedEmail?.id === emailId) setSelectedEmail(result.data)
        await fetchData()
      }
    } finally {
      setProcessingId(null)
    }
  }

  const handleDelete = async (emailId: string) => {
    try {
      await officeService.deleteEmail(emailId)
      setSelectedEmail(null)
      await fetchData()
    } catch {
      // Error shown via service toast
    }
  }

  const handleSyncAccount = async (accountId: string) => {
    setSyncingAccountId(accountId)
    try {
      await officeService.syncEmailAccount(accountId)
      await fetchData()
    } finally {
      setSyncingAccountId(null)
    }
  }

  const filteredEmails = categoryFilter === 'all' ? emails : emails.filter((e) => e.category === categoryFilter)

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-64 bg-gray-200 rounded animate-pulse mt-2" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="h-4 w-20 bg-gray-200 rounded animate-pulse mb-2" />
              <div className="h-8 w-12 bg-gray-200 rounded animate-pulse" />
            </div>
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
          <h1 className="text-2xl font-bold text-gray-900">Email Support</h1>
          <p className="mt-1 text-sm text-gray-500">Manage incoming customer emails and agent responses.</p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Email
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
          <StatCard label="Total" value={stats.total} color="blue"
            icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" /></svg>}
          />
          <StatCard label="New" value={stats.new} color="amber"
            icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
          />
          <StatCard label="Processing" value={stats.processing} color="amber"
            icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>}
          />
          <StatCard label="Replied" value={stats.replied} color="green"
            icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
          />
          <StatCard label="Failed" value={stats.failed} color="red"
            icon={<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>}
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900">Inbox</h2>
              <div className="flex items-center gap-2">
                <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="text-xs px-2 py-1 border border-gray-200 rounded-md bg-white text-gray-600 focus:outline-none focus:ring-1 focus:ring-primary-500">
                  <option value="all">All categories</option>
                  <option value="support">Support</option>
                  <option value="billing">Billing</option>
                  <option value="technical">Technical</option>
                  <option value="general">General</option>
                  <option value="spam">Spam</option>
                </select>
              </div>
            </div>
            {filteredEmails.length === 0 ? (
              <div className="p-12 text-center">
                <svg className="mx-auto h-10 w-10 text-gray-300" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                </svg>
                <h3 className="mt-3 text-sm font-medium text-gray-900">No emails yet</h3>
                <p className="mt-1 text-sm text-gray-500">Create a new email to get started.</p>
                <button type="button" onClick={() => setShowCreateModal(true)} className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                  New Email
                </button>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {filteredEmails.map((email) => (
                  <button
                    key={email.id}
                    type="button"
                    onClick={() => setSelectedEmail(email)}
                    className="w-full text-left px-5 py-3 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-900 truncate">{email.subject}</span>
                          {email.category && (
                            <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 ${CATEGORY_COLORS[email.category] ?? 'bg-gray-50 text-gray-600'}`}>
                              {email.category}
                            </span>
                          )}
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium shrink-0 ${EMAIL_STATUS_COLORS[email.status] ?? 'bg-gray-100 text-gray-500'}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${EMAIL_STATUS_DOT[email.status] ?? 'bg-gray-400'}`} />
                            {email.status}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5 truncate">From: {email.from_address}</p>
                        <p className="text-xs text-gray-400 mt-0.5 truncate">{email.body}</p>
                      </div>
                      <span className="text-[10px] text-gray-400 shrink-0">
                        {new Date(email.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-1 space-y-6">
          {accounts.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-900">Connected Accounts</h2>
                <Link to="/email-accounts" className="text-xs font-medium text-primary-600 hover:text-primary-700">Manage</Link>
              </div>
              <div className="divide-y divide-gray-100">
                {accounts.map((account) => (
                  <div key={account.id} className="px-5 py-3 flex items-center gap-3">
                    <span className="flex items-center justify-center h-8 w-8 rounded-full bg-primary-100 text-primary-700 text-xs font-medium shrink-0">
                      {account.email_address.charAt(0).toUpperCase()}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-900 truncate">{account.email_address}</p>
                      <p className="text-[10px] text-gray-400">
                        {account.last_sync_at ? `Synced ${new Date(account.last_sync_at).toLocaleTimeString()}` : 'Never synced'}
                      </p>
                    </div>
                    <button type="button" onClick={() => handleSyncAccount(account.id)} disabled={syncingAccountId === account.id || !account.is_active} className="p-1 rounded text-gray-400 hover:text-primary-600 hover:bg-primary-50 transition-colors disabled:opacity-50" title="Sync now">
                      <svg className={`h-3.5 w-3.5 ${syncingAccountId === account.id ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-900">Recent Activity</h2>
            </div>
            {activities.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-sm text-gray-500">No activity yet</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
                {activities.map((activity) => (
                  <div key={activity.id} className="px-5 py-3">
                    <p className="text-xs font-medium text-gray-700">{activity.activity_type}</p>
                    {activity.description && (
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{activity.description}</p>
                    )}
                    <p className="text-[10px] text-gray-400 mt-1">
                      {new Date(activity.created_at).toLocaleString()}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {showCreateModal && (
        <CreateEmailModal onClose={() => setShowCreateModal(false)} onSubmit={handleCreate} />
      )}

      {selectedEmail && (
        <EmailDetailModal
          email={selectedEmail}
          isProcessing={processingId === selectedEmail.id}
          onClose={() => setSelectedEmail(null)}
          onProcess={() => handleProcess(selectedEmail.id)}
          onDelete={() => handleDelete(selectedEmail.id)}
        />
      )}
    </div>
  )
}

function CreateEmailModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (data: CreateEmailRequest) => Promise<void> }) {
  const [fromAddress, setFromAddress] = useState('')
  const [toAddress, setToAddress] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!fromAddress.trim() || !subject.trim() || !body.trim()) {
      setFormError('From, subject, and body are required')
      return
    }
    setIsSubmitting(true)
    setFormError(null)
    try {
      await onSubmit({
        from_address: fromAddress.trim(),
        to_address: toAddress.trim() || 'support@ai-office.com',
        subject: subject.trim(),
        body: body.trim(),
      })
      onClose()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create email')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">New Email</h2>
          <button type="button" onClick={onClose} className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          {formError && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">{formError}</div>
          )}
          <div>
            <label htmlFor="email-from" className="block text-sm font-medium text-gray-700 mb-1">From <span className="text-red-500">*</span></label>
            <input id="email-from" type="email" value={fromAddress} onChange={(e) => setFromAddress(e.target.value)} placeholder="customer@example.com" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
          </div>
          <div>
            <label htmlFor="email-to" className="block text-sm font-medium text-gray-700 mb-1">To</label>
            <input id="email-to" type="email" value={toAddress} onChange={(e) => setToAddress(e.target.value)} placeholder="support@ai-office.com" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
          </div>
          <div>
            <label htmlFor="email-subject" className="block text-sm font-medium text-gray-700 mb-1">Subject <span className="text-red-500">*</span></label>
            <input id="email-subject" type="text" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="How can we help?" className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500" />
          </div>
          <div>
            <label htmlFor="email-body" className="block text-sm font-medium text-gray-700 mb-1">Body <span className="text-red-500">*</span></label>
            <textarea id="email-body" value={body} onChange={(e) => setBody(e.target.value)} rows={5} placeholder="Customer message..." className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 resize-none" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} disabled={isSubmitting} className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={isSubmitting || !fromAddress.trim() || !subject.trim() || !body.trim()} className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
              {isSubmitting ? 'Creating...' : 'Create Email'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function EmailDetailModal({ email, isProcessing, onClose, onProcess, onDelete }: {
  email: EmailMessage
  isProcessing: boolean
  onClose: () => void
  onProcess: () => void
  onDelete: () => void
}) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden max-h-[85vh] flex flex-col">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between shrink-0">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-gray-900 truncate">{email.subject}</h2>
            <p className="text-xs text-gray-500 mt-0.5">From: {email.from_address}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${EMAIL_STATUS_COLORS[email.status] ?? 'bg-gray-100 text-gray-500'}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${EMAIL_STATUS_DOT[email.status] ?? 'bg-gray-400'}`} />
              {email.status}
            </span>
            <button type="button" onClick={onClose} className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        <div className="px-5 py-4 overflow-y-auto flex-1">
          <div className="mb-4">
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Message</h3>
            <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap">{email.body}</div>
          </div>
          {email.draft_response && (
            <div className="mb-4">
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">AI Draft Response</h3>
              <div className="bg-primary-50 border border-primary-100 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap">{email.draft_response}</div>
            </div>
          )}
          <div className="text-xs text-gray-400">
            Received: {new Date(email.created_at).toLocaleString()}
          </div>
        </div>
        <div className="px-5 py-3 bg-gray-50 border-t border-gray-200 flex justify-end gap-2 shrink-0">
          <button type="button" onClick={onDelete} className="px-4 py-2 text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors">
            Delete
          </button>
          {(email.status === 'new' || email.status === 'failed') && (
            <button type="button" onClick={onProcess} disabled={isProcessing} className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors">
              {isProcessing ? 'Processing...' : 'Process with AI'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default EmailDashboardPage
