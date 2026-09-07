import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/useAuthStore'

const HomePage = () => {
  const { isAuthenticated } = useAuthStore()

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
      <div className="text-center">
        <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white tracking-tight">
          Welcome to AI Virtual Office
        </h1>
        <p className="mt-4 sm:mt-6 text-lg sm:text-xl text-white/70 max-w-2xl mx-auto">
          Your AI-powered virtual workplace platform
        </p>
        <div className="mt-8 sm:mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          {isAuthenticated ? (
            <>
              <Link
                to="/office"
                className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 rounded-lg bg-indigo-600 text-white font-medium text-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 transition-colors"
              >
                Enter Virtual Office
              </Link>
              <Link
                to="/dashboard"
                className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 rounded-lg border border-indigo-500/40 text-indigo-300 font-medium text-sm hover:bg-indigo-500/15 hover:text-indigo-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 transition-colors"
              >
                View Dashboard
              </Link>
            </>
          ) : (
            <Link
              to="/login"
              className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 rounded-lg bg-indigo-600 text-white font-medium text-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 transition-colors"
            >
              Sign in with Google
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}

export default HomePage
