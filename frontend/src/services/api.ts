import type { ApiResponse } from '../types'

const API_BASE_URL = '/api/v1/'

class ApiService {
  private getToken(): string | null {
    return localStorage.getItem('token')
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const token = this.getToken()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers,
      })

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null)
        const message = errorBody?.detail ?? `HTTP error! status: ${response.status}`
        console.error(`[API] ${options.method || 'GET'} ${endpoint} -> ${response.status}`, message)
        throw new Error(message)
      }

      if (response.status === 204) {
        return { success: true }
      }

      const data = await response.json()
      return { success: true, data }
    } catch (error) {
      console.error(`[API] ${options.method || 'GET'} ${endpoint} failed:`, error)
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      }
    }
  }

  async get<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'GET' })
  }

  async post<T>(endpoint: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async put<T>(endpoint: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }

  async postForm<T>(endpoint: string, data: Record<string, string>): Promise<ApiResponse<T>> {
    const token = this.getToken()
    const headers: Record<string, string> = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    try {
      const formData = new URLSearchParams()
      for (const [key, value] of Object.entries(data)) {
        formData.append(key, value)
      }

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          ...headers,
        },
        body: formData.toString(),
      })

      if (!response.ok) {
        const errorBody = await response.json().catch(() => null)
        const message = errorBody?.detail ?? `HTTP error! status: ${response.status}`
        console.error(`[API] POST ${endpoint} -> ${response.status}`, message)
        throw new Error(message)
      }

      const result = await response.json()
      return { success: true, data: result }
    } catch (error) {
      console.error(`[API] POST ${endpoint} failed:`, error)
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      }
    }
  }
}

export const api = new ApiService()
