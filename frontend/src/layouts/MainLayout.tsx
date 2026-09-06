import { useState, useEffect, useRef } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/useAuthStore'
import { useRealtimeStore, initRealtime } from '../stores/useRealtimeStore'
import Toolbar from '../components/Toolbar'
import { CircleUserRound } from 'lucide-react'
import { cn } from '../lib/utils'

function UserAccount() {
  const [open, setOpen] = useState(false)
  const { user, isAuthenticated, logout } = useAuthStore()
  const navigate = useNavigate()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  if (!isAuthenticated || !user) {
    return (
      <NavLink
        to="/login"
        className={cn(
          "flex items-center gap-2 px-4 py-2 rounded-xl border shadow-sm",
          "text-sm font-medium text-gray-600 bg-white",
          "border-gray-200 hover:bg-gray-50 hover:text-gray-900",
          "transition-all duration-200 no-underline"
        )}
      >
        <CircleUserRound className="h-4 w-4" />
        Sign in
      </NavLink>
    )
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-2 px-3 py-1.5 rounded-xl border shadow-sm",
          "bg-white border-gray-200 hover:bg-gray-50",
          "transition-all duration-200",
          "focus:outline-none focus:ring-2 focus:ring-primary-500/30"
        )}
      >
        {user.avatar_url ? (
          <img src={user.avatar_url} alt="" className="h-7 w-7 rounded-full" />
        ) : (
          <span className="flex items-center justify-center h-7 w-7 rounded-full bg-primary-100 text-primary-700 text-xs font-bold">
            {user.name.charAt(0).toUpperCase()}
          </span>
        )}
        <span className="text-sm font-medium text-gray-700 max-w-[100px] truncate hidden lg:inline">
          {user.name}
        </span>
        <svg
          className={cn("h-4 w-4 text-gray-400 transition-transform", open && "rotate-180")}
          fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl border border-gray-200 shadow-lg py-1 z-50">
            <div className="px-4 py-3 border-b border-gray-100">
              <p className="text-sm font-medium text-gray-900 truncate">{user.name}</p>
              {user.email && (
                <p className="text-xs text-gray-500 truncate">{user.email}</p>
              )}
              {user.role && (
                <span className="inline-block mt-1 px-2 py-0.5 text-xs font-medium bg-primary-50 text-primary-700 rounded-full capitalize">
                  {user.role}
                </span>
              )}
            </div>
            <NavLink
              to="/profile"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 no-underline"
            >
              <CircleUserRound className="h-4 w-4 text-gray-400" />
              Profile
            </NavLink>
            <button
              type="button"
              onClick={() => { logout(); setOpen(false); navigate('/') }}
              className="flex items-center gap-2 w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              <svg className="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
              </svg>
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  )
}

const MainLayout = () => {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { user, isAuthenticated, token } = useAuthStore()
  const navigate = useNavigate()
  const { connected, unreadNotifications, pendingApprovals, connect, connectUser, disconnect } = useRealtimeStore()

  useEffect(() => {
    if (isAuthenticated && token) {
      initRealtime(token)
      connect('ceo-dashboard', token)
      if (user?.id) {
        connectUser(user.id, token)
      }
    }
    return () => { disconnect() }
  }, [isAuthenticated, token, user?.id])

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-4">
            <NavLink to="/" className="flex items-center gap-2 shrink-0 no-underline">
              <span className="text-xl font-bold text-primary-600">AI Virtual Office</span>
            </NavLink>

            <div className="hidden md:block flex-1 max-w-4xl" />

            <div className="hidden md:block">
              <UserAccount />
            </div>

            <button
              type="button"
              className="md:hidden inline-flex items-center justify-center p-2 rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-expanded={mobileOpen}
              aria-label="Toggle navigation menu"
            >
              {mobileOpen ? (
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <nav className="md:hidden border-t border-gray-200 px-4 py-2 space-y-1" aria-label="Mobile navigation">
            {[
              { to: '/', label: 'Home' },
              { to: '/office', label: 'Office' },
              { to: '/dashboard', label: 'Dashboard' },
              { to: '/ceo/inbox', label: 'Inbox' },
              { to: '/ceo', label: 'CEO Dashboard' },
              { to: '/agents', label: 'Agents' },
              { to: '/tools', label: 'Tools' },
              { to: '/permissions', label: 'Permissions' },
              { to: '/approvals', label: 'Approvals' },
              { to: '/risk-settings', label: 'Risk' },
              { to: '/tasks', label: 'Tasks' },
              { to: '/knowledge', label: 'Knowledge' },
              { to: '/integrations', label: 'Integrations' },
              { to: '/emails', label: 'Emails' },
            ].map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  `block px-3 py-2 rounded-md text-base font-medium transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            <div className="border-t border-gray-200 pt-2 mt-2">
              {isAuthenticated && user ? (
                <>
                  <NavLink
                    to="/profile"
                    onClick={() => setMobileOpen(false)}
                    className="block px-3 py-2 rounded-md text-base font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 no-underline"
                  >
                    Profile
                  </NavLink>
                  <button
                    type="button"
                    onClick={() => { useAuthStore.getState().logout(); setMobileOpen(false); navigate('/') }}
                    className="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                  >
                    Sign out
                  </button>
                </>
              ) : (
                <NavLink
                  to="/login"
                  onClick={() => setMobileOpen(false)}
                  className="block px-3 py-2 rounded-md text-base font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 no-underline"
                >
                  Sign in with Google
                </NavLink>
              )}
            </div>
          </nav>
        )}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <Toolbar
        connected={connected}
        unreadNotifications={unreadNotifications}
        pendingApprovals={pendingApprovals}
      />
    </div>
  )
}

export default MainLayout
