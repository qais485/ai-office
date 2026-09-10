import { useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import HomePage from './pages/HomePage'
import OfficePage from './pages/OfficePage'
import DashboardPage from './pages/DashboardPage'
import AgentsPage from './pages/AgentsPage'
import ToolsPage from './pages/ToolsPage'
import PermissionsPage from './pages/PermissionsPage'
import ApprovalsPage from './pages/ApprovalsPage'
import RiskSettingsPage from './pages/RiskSettingsPage'
import TasksPage from './pages/TasksPage'
import KnowledgePage from './pages/KnowledgePage'
import CEOPage from './pages/CEOPage'
import CEOInboxPage from './pages/CEOInboxPage'
import EmailDashboardPage from './pages/EmailDashboardPage'
import EmailAccountsPage from './pages/EmailAccountsPage'
import IntegrationsPage from './pages/IntegrationsPage'
import OAuth2CallbackPage from './pages/OAuth2CallbackPage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import PrivacyPolicyPage from './pages/PrivacyPolicyPage'
import TermsOfServicePage from './pages/TermsOfServicePage'
import ProtectedRoute from './components/ProtectedRoute'
import { useAuthStore } from './stores/useAuthStore'

function NotFoundPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
      <h1 className="text-4xl font-bold text-white">404</h1>
      <p className="mt-2 text-sm text-white/50">Page not found.</p>
      <Link to="/" className="mt-4 inline-block text-sm font-medium text-indigo-400 hover:text-indigo-300">
        Go home
      </Link>
    </div>
  )
}

function App() {
  const initAuth = useAuthStore((s) => s.initAuth)

  useEffect(() => {
    initAuth()
  }, [initAuth])

  return (
    <Router>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<HomePage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="privacy" element={<PrivacyPolicyPage />} />
          <Route path="terms" element={<TermsOfServicePage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="office" element={<OfficePage />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="agents" element={<AgentsPage />} />
            <Route path="tools" element={<ToolsPage />} />
            <Route path="permissions" element={<PermissionsPage />} />
            <Route path="approvals" element={<ApprovalsPage />} />
            <Route path="risk-settings" element={<RiskSettingsPage />} />
            <Route path="tasks" element={<TasksPage />} />
            <Route path="knowledge" element={<KnowledgePage />} />
            <Route path="ceo" element={<CEOPage />} />
            <Route path="ceo/inbox" element={<CEOInboxPage />} />
            <Route path="integrations" element={<IntegrationsPage />} />
            <Route path="emails" element={<EmailDashboardPage />} />
            <Route path="email-accounts" element={<EmailAccountsPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
          <Route path="integrations/callback" element={<OAuth2CallbackPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Router>
  )
}

export default App
