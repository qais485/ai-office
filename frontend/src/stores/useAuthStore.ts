import { create } from 'zustand'
import type { User } from '../types'
import { authService } from '../services/auth'

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  googleLogin: (credential: string) => Promise<boolean>
  logout: () => void
  initAuth: () => Promise<void>
  updateProfile: (name: string) => Promise<boolean>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('token'),
  isAuthenticated: false,
  isLoading: false,
  error: null,

  googleLogin: async (credential) => {
    set({ isLoading: true, error: null })
    const result = await authService.googleLogin(credential)
    if (!result.success || !result.data) {
      set({ isLoading: false, error: result.error ?? 'Google login failed' })
      return false
    }
    localStorage.setItem('token', result.data.access_token)
    const userResult = await authService.getMe()
    if (!userResult.success || !userResult.data) {
      set({ isLoading: false, error: 'Failed to load user profile' })
      localStorage.removeItem('token')
      return false
    }
    set({
      user: userResult.data,
      token: result.data.access_token,
      isAuthenticated: true,
      isLoading: false,
    })
    return true
  },

  logout: () => {
    localStorage.removeItem('token')
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      error: null,
    })
  },

  initAuth: async () => {
    const token = localStorage.getItem('token')
    if (!token) {
      console.log('[Auth] no token found, skipping init')
      return
    }
    set({ isLoading: true })
    const result = await authService.getMe()
    if (!result.success || !result.data) {
      console.warn('[Auth] token invalid or expired, clearing:', result.error)
      localStorage.removeItem('token')
      set({ isLoading: false, token: null })
      return
    }
    console.log('[Auth] authenticated as', result.data.name || result.data.email)
    set({
      user: result.data,
      token,
      isAuthenticated: true,
      isLoading: false,
    })
  },

  updateProfile: async (name) => {
    set({ isLoading: true, error: null })
    const result = await authService.updateProfile({ name })
    if (!result.success || !result.data) {
      set({ isLoading: false, error: result.error ?? 'Update failed' })
      return false
    }
    set({ user: result.data, isLoading: false })
    return true
  },

  clearError: () => set({ error: null }),
}))
