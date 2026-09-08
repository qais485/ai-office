import { useState, type FormEvent } from 'react'
import { useAuthStore } from '../stores/useAuthStore'

const ProfilePage = () => {
  const { user, updateProfile, isLoading, error, clearError } = useAuthStore()

  const [name, setName] = useState(user?.name ?? '')
  const [profileSaved, setProfileSaved] = useState(false)

  const handleProfileSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setProfileSaved(false)
    const success = await updateProfile(name)
    if (success) {
      setProfileSaved(true)
    }
  }

  if (!user) return null

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white">Profile</h1>
        <p className="mt-2 text-white/70">Manage your account settings</p>
      </div>

      <div className="bg-white/[0.03] rounded-xl border border-white/10 p-6">
        <h2 className="text-lg font-semibold text-white mb-1">Personal information</h2>
        <p className="text-sm text-white/50 mb-6">Update your name and profile details.</p>

        {error && (
          <div className="bg-red-500/10 border border-red-500/25 text-red-400 text-sm rounded-lg px-4 py-3 mb-4">
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

        {profileSaved && (
          <div className="bg-green-500/10 border border-green-500/25 text-green-400 text-sm rounded-lg px-4 py-3 mb-4">
            Profile updated successfully.
          </div>
        )}

        <form onSubmit={handleProfileSubmit} className="space-y-4">
          <div>
            <label htmlFor="profile-name" className="block text-sm font-medium text-white/80 mb-1">
              Name
            </label>
            <input
              id="profile-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-white/30 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/30"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-white/80 mb-1">Email</label>
            <input
              type="email"
              value={user.email}
              disabled
              className="w-full px-3 py-2 border border-white/10 rounded-lg text-sm bg-white/[0.04] text-white/50 cursor-not-allowed"
            />
            <p className="mt-1 text-xs text-white/40">Email is managed by your Google account.</p>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white font-medium text-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? 'Saving...' : 'Save changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default ProfilePage
