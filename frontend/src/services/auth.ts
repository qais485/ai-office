import { api } from './api'
import type { User, TokenResponse, UpdateProfileRequest } from '../types'

export const authService = {
  async googleLogin(credential: string) {
    return api.post<TokenResponse>('auth/google', { credential })
  },

  async getMe() {
    return api.get<User>('auth/me')
  },

  async updateProfile(data: UpdateProfileRequest) {
    return api.put<User>('auth/me', data)
  },
}
