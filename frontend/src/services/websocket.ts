/**
 * WebSocket client with auto-reconnect, heartbeat pong, and event dispatching.
 */

import { API_WS_BASE_URL } from '../lib/apiConfig'

type MessageHandler = (data: any) => void

interface WSOptions {
  reconnectInterval?: number
  maxReconnectAttempts?: number
  heartbeatInterval?: number
}

const DEFAULT_OPTIONS: Required<WSOptions> = {
  reconnectInterval: 3000,
  maxReconnectAttempts: 10,
  heartbeatInterval: 30000,
}

class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string = ''
  private handlers: Map<string, Set<MessageHandler>> = new Map()
  private reconnectAttempts: number = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private options: Required<WSOptions>
  private intentionalClose: boolean = false
  private _connected: boolean = false

  constructor(options?: WSOptions) {
    this.options = { ...DEFAULT_OPTIONS, ...options }
  }

  get connected(): boolean {
    return this._connected
  }

  connect(roomId: string, token?: string): void {
    this.intentionalClose = false
    const params = token ? `?token=${encodeURIComponent(token)}` : ''
    this.url = `${API_WS_BASE_URL}/ws/${roomId}${params}`
    this._open()
  }

  connectDashboard(token?: string): void {
    this.intentionalClose = false
    const params = token ? `?token=${encodeURIComponent(token)}` : ''
    this.url = `${API_WS_BASE_URL}/ws/dashboard${params}`
    this._open()
  }

  connectUser(userId: string, token?: string): void {
    this.intentionalClose = false
    const params = token ? `?token=${encodeURIComponent(token)}` : ''
    this.url = `${API_WS_BASE_URL}/ws/user/${userId}${params}`
    this._open()
  }

  private _open(): void {
    if (this.ws) {
      this.ws.close()
    }

    try {
      this.ws = new WebSocket(this.url)
    } catch (e) {
      this._scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      this._connected = true
      this.reconnectAttempts = 0
      this._startHeartbeat()
      console.log(`[WS] connected to ${this.url}`)
      this._dispatch('connected', {})
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'ping') {
          this._send({ type: 'pong' })
          return
        }
        this._dispatch(msg.type || 'message', msg)
      } catch {
        this._dispatch('message', { data: event.data })
      }
    }

    this.ws.onclose = (event) => {
      this._connected = false
      this._stopHeartbeat()
      console.log(`[WS] disconnected (code=${event.code} reason=${event.reason || 'none'})`)
      this._dispatch('disconnected', {})
      if (!this.intentionalClose) {
        this._scheduleReconnect()
      }
    }

    this.ws.onerror = () => {
      console.error(`[WS] error connecting to ${this.url}`)
      // onclose will fire after onerror
    }
  }

  private _send(data: object): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  private _startHeartbeat(): void {
    this._stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      this._send({ type: 'pong' })
    }, this.options.heartbeatInterval)
  }

  private _stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      console.error(`[WS] reconnect failed after ${this.reconnectAttempts} attempts`)
      this._dispatch('reconnect_failed', {})
      return
    }
    this.reconnectAttempts++
    const delay = this.options.reconnectInterval * Math.min(this.reconnectAttempts, 5)
    console.log(`[WS] reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    this.reconnectTimer = setTimeout(() => this._open(), delay)
  }

  on(type: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    this.handlers.get(type)!.add(handler)
    return () => {
      this.handlers.get(type)?.delete(handler)
    }
  }

  off(type: string, handler: MessageHandler): void {
    this.handlers.get(type)?.delete(handler)
  }

  private _dispatch(type: string, data: any): void {
    const handlers = this.handlers.get(type)
    if (handlers) {
      handlers.forEach((h) => {
        try { h(data) } catch (e) { console.error(`WS handler error [${type}]:`, e) }
      })
    }
    // Also dispatch to wildcard handlers
    const wildcards = this.handlers.get('*')
    if (wildcards) {
      wildcards.forEach((h) => {
        try { h({ type, ...data }) } catch (e) { console.error('WS wildcard handler error:', e) }
      })
    }
  }

  disconnect(): void {
    this.intentionalClose = true
    this._stopHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this._connected = false
  }

  send(data: object): void {
    this._send(data)
  }
}

export const wsClient = new WebSocketClient()
