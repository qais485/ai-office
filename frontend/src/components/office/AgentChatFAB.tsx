import { useState, useRef, useEffect } from 'react'
import { officeService } from '../../services/office'

interface ChatMessage {
  role: 'user' | 'agent'
  text: string
  toolUsed?: string | null
}

interface AgentChatFABProps {
  agentId: string | null
  agentName: string
}

export default function AgentChatFAB({ agentId, agentName }: AgentChatFABProps) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending])

  const send = async () => {
    const text = input.trim()
    if (!text || !agentId || sending) return

    setInput('')
    setMessages((m) => [...m, { role: 'user', text }])
    setSending(true)
    try {
      const res = await officeService.chatWithAgent(agentId, text)
      const reply = res.data?.reply
      setMessages((m) => [
        ...m,
        {
          role: 'agent',
          text: reply || '(Agent is still working — check back in a moment)',
          toolUsed: res.data?.tool_used ?? null,
        },
      ])
    } catch {
      setMessages((m) => [...m, { role: 'agent', text: 'Failed to reach the agent. Is the backend running?' }])
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      {/* Floating chat button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          title={`Chat with ${agentName}`}
          className="fixed bottom-6 right-6 z-40 h-14 w-14 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white shadow-2xl shadow-indigo-900/50 flex items-center justify-center transition-all hover:scale-105"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
          </svg>
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-40 w-[380px] max-w-[calc(100vw-2rem)] h-[520px] max-h-[calc(100vh-6rem)] rounded-2xl bg-[#0d0d1a] border border-white/10 shadow-2xl shadow-black/60 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="px-4 py-3 bg-gradient-to-r from-indigo-500/15 to-purple-500/15 border-b border-white/10 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="h-8 w-8 rounded-full bg-indigo-500/25 flex items-center justify-center text-indigo-200 text-sm font-bold shrink-0">
                {agentName.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-white truncate">{agentName}</p>
                <p className="text-[10px] text-white/40">
                  {sending ? 'typing…' : 'AI Assistant · replies in ~15-30s'}
                </p>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="text-white/40 hover:text-white shrink-0">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 && (
              <div className="text-center py-10 px-4">
                <p className="text-sm text-white/40">Ask anything — files, knowledge, emails.</p>
                <p className="text-xs text-white/25 mt-1">e.g. "Create a meeting-notes file in Drive"</p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm whitespace-pre-wrap break-words ${
                    m.role === 'user'
                      ? 'bg-indigo-600 text-white rounded-br-sm'
                      : 'bg-white/8 text-white/90 rounded-bl-sm border border-white/5'
                  }`}
                >
                  {m.text}
                  {m.toolUsed && (
                    <span className="block mt-1.5 text-[10px] text-white/40">via {m.toolUsed}</span>
                  )}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="bg-white/8 rounded-2xl rounded-bl-sm px-4 py-3 flex gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-white/40 animate-bounce [animation-delay:0ms]" />
                  <span className="h-2 w-2 rounded-full bg-white/40 animate-bounce [animation-delay:150ms]" />
                  <span className="h-2 w-2 rounded-full bg-white/40 animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="p-3 border-t border-white/10 shrink-0">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
                disabled={sending || !agentId}
                placeholder={agentId ? 'Type a message…' : 'No agent in this room'}
                className="flex-1 px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder-white/25 focus:outline-none focus:border-indigo-500/50 disabled:opacity-50"
              />
              <button
                onClick={send}
                disabled={sending || !input.trim() || !agentId}
                className="px-3.5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-xl transition-colors shrink-0"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
