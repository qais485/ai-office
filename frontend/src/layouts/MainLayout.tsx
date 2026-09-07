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
          "flex items-center gap-2 px-4 py-2 rounded-xl border",
          "text-sm font-medium text-white/80 bg-white/5",
          "border-white/10 hover:bg-white/10 hover:text-white",
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
          "flex items-center gap-2 px-3 py-1.5 rounded-xl border",
          "bg-white/5 border-white/10 hover:bg-white/10",
          "transition-all duration-200",
          "focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
        )}
      >
        {user.avatar_url ? (
          <img src={user.avatar_url} alt="" className="h-7 w-7 rounded-full" />
        ) : (
          <span className="flex items-center justify-center h-7 w-7 rounded-full bg-indigo-500/15 text-indigo-300 text-xs font-bold">
            {user.name.charAt(0).toUpperCase()}
          </span>
        )}
        <span className="text-sm font-medium text-white/80 max-w-[100px] truncate hidden lg:inline">
          {user.name}
        </span>
        <svg
          className={cn("h-4 w-4 text-white/40 transition-transform", open && "rotate-180")}
          fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-2 w-56 bg-[#0d0d1a] rounded-xl border border-white/10 shadow-2xl shadow-black/50 py-1 z-50">
            <div className="px-4 py-3 border-b border-white/6">
              <p className="text-sm font-medium text-white truncate">{user.name}</p>
              {user.email && (
                <p className="text-xs text-white/40 truncate">{user.email}</p>
              )}
              {user.role && (
                <span className="inline-block mt-1 px-2 py-0.5 text-xs font-medium bg-indigo-500/15 text-indigo-300 rounded-full capitalize">
                  {user.role}
                </span>
              )}
            </div>
            <NavLink
              to="/profile"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2 text-sm text-white/70 hover:bg-white/5 hover:text-white no-underline"
            >
              <CircleUserRound className="h-4 w-4 text-white/40" />
              Profile
            </NavLink>
            <button
              type="button"
              onClick={() => { logout(); setOpen(false); navigate('/') }}
              className="flex items-center gap-2 w-full px-4 py-2 text-sm text-white/70 hover:bg-white/5 hover:text-white"
            >
              <svg className="h-4 w-4 text-white/40" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
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
      initRealtime()
      connect('ceo-dashboard', token)
      if (user?.id) {
        connectUser(user.id, token)
      }
    }
    return () => { disconnect() }
  }, [isAuthenticated, token, user?.id])

  return (
    <div className="min-h-screen bg-[#06060f] flex flex-col">
      <header className="bg-[#06060f]/85 backdrop-blur-xl border-b border-white/6 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-4">
            <NavLink to="/" className="flex items-center gap-2 shrink-0 no-underline">
              <span className="text-xl font-bold text-white tracking-tight">
                AI Virtual <span className="text-indigo-400">Office</span>
              </span>
            </NavLink>

            <div className="hidden md:block flex-1 max-w-4xl" />

            <div className="hidden md:block">
              <UserAccount />
            </div>

            <button
              type="button"
              className="md:hidden inline-flex items-center justify-center p-2 rounded-md text-white/60 hover:text-white hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500"
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
          <nav className="md:hidden border-t border-white/6 px-4 py-2 space-y-1 bg-[#06060f]" aria-label="Mobile navigation">
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
                      ? 'bg-indigo-500/15 text-indigo-300'
                      : 'text-white/60 hover:text-white hover:bg-white/5'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            <div className="border-t border-white/10 pt-2 mt-2">
              {isAuthenticated && user ? (
                <>
                  <NavLink
                    to="/profile"
                    onClick={() => setMobileOpen(false)}
                    className="block px-3 py-2 rounded-md text-base font-medium text-white/60 hover:text-white hover:bg-white/5 no-underline"
                  >
                    Profile
                  </NavLink>
                  <button
                    type="button"
                    onClick={() => { useAuthStore.getState().logout(); setMobileOpen(false); navigate('/') }}
                    className="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-white/60 hover:text-white hover:bg-white/5"
                  >
                    Sign out
                  </button>
                </>
              ) : (
                <NavLink
                  to="/login"
                  onClick={() => setMobileOpen(false)}
                  className="block px-3 py-2 rounded-md text-base font-medium text-white/60 hover:text-white hover:bg-white/5 no-underline"
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
