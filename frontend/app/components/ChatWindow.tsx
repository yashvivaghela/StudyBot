'use client'

import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import SessionBrief from '@/app/components/SessionBrief'

const API = 'http://localhost:8000'

interface Message {
  id?: number
  role: string
  content: string
}

interface Props {
  topicId: number
  topicName: string
  initialMessages: Message[]
  prefillMessage?: string
  onPrefillUsed?: () => void
  onTaskUpdate?: () => void
  
}
interface PlanChange {
  reason: string
  preview?: {
    week_number: number
    focus_area: string
    tasks: string[]
  }[]
  summary?: string
  confirmed?: boolean
  error?: string
}

export default function ChatWindow({ topicId, topicName, initialMessages, prefillMessage, onPrefillUsed ,onTaskUpdate}: Props) {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [retrieving, setRetrieving] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [pendingPlanChange, setPendingPlanChange] = useState<PlanChange | null>(null)
  const [applyingPlanChange, setApplyingPlanChange] = useState(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (prefillMessage) {
      setInput(prefillMessage)
      onPrefillUsed?.()
    }
  }, [prefillMessage])
 async function confirmPlanChange() {
  if (!pendingPlanChange) return
  setApplyingPlanChange(true)

  // Step 1 — if no preview yet, fetch preview first
  if (!pendingPlanChange.preview) {
    try {
      const res = await fetch(`${API}/topics/${topicId}/preview-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: pendingPlanChange.reason })
      })
      if (!res.ok) {
        setPendingPlanChange({
          ...pendingPlanChange,
          error: 'AI is overloaded. Please wait a minute and try again.'
        })
        setApplyingPlanChange(false)
        return
      }
      const data = await res.json()
      // Update pill with preview
      setPendingPlanChange({
        ...pendingPlanChange,
        preview: data.preview,
        summary: data.summary
      })
      setApplyingPlanChange(false)
    } catch (e) {
      setPendingPlanChange({
        ...pendingPlanChange,
        error: 'Something went wrong. Please try again.'
      })
      setApplyingPlanChange(false)
    }
    return
  }

  // Step 2 — preview shown, now actually save
  try {
    const res = await fetch(`${API}/topics/${topicId}/adjust-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: pendingPlanChange.reason,cached_weeks: pendingPlanChange.preview,  // ← send the preview data
    summary: pendingPlanChange.summary })
    })
    if (!res.ok) {
      setPendingPlanChange({
        ...pendingPlanChange,
        error: 'AI is overloaded. Please wait a minute and try again.'
      })
      setApplyingPlanChange(false)
      return
    }

    const data = await res.json()
    setPendingPlanChange(null)
    setApplyingPlanChange(false)
    onTaskUpdate?.()

    setMessages(prev => [...prev, {
      role: 'assistant',
      content: `✅ Plan updated! ${data.summary}`
    }])
  } catch (e) {
    setPendingPlanChange({
      ...pendingPlanChange,
      error: 'Something went wrong. Please try again.'
    })
    setApplyingPlanChange(false)
  }
}

  async function sendMessage() {
    if (!input.trim() || streaming) return

    const userMessage = input.trim()
    setInput('')
    setPendingPlanChange(null)

    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setRetrieving(true)
    

    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_id: topicId, message: userMessage })
      })

      setRetrieving(false)
      setStreaming(true)

      setMessages(prev => [...prev, { role: 'assistant', content: '' }])

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let hasContent = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        if (chunk.includes('__PLAN_CHANGE__') && chunk.includes('__PLANEND__')) {
    try {
      const signalStart = chunk.indexOf('__PLAN_CHANGE__')
      const signalEnd = chunk.indexOf('__PLANEND__') + '__PLANEND__'.length
      const signal = chunk.slice(signalStart, signalEnd)
      const jsonStr = signal.replace('__PLAN_CHANGE__', '').replace('__PLANEND__', '').trim()
      const planData = JSON.parse(jsonStr)
      setPendingPlanChange(planData)
      
      // Render anything after the signal
      const remainder = chunk.slice(signalEnd)
      if (remainder) {
        hasContent = true
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: updated[updated.length - 1].content + remainder
          }
          return updated
        })
      }
      // invalidate cache is new message is there 
      sessionStorage.removeItem(`brief_${topicId}`)
      sessionStorage.removeItem(`brief_time_${topicId}`)
    } catch (e) {
      console.error('Failed to parse plan change signal', e)
    }
    continue
  }

        if (chunk) {
          hasContent = true
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: 'assistant',
              content: updated[updated.length - 1].content + chunk
            }
            return updated
          })
        }
      }

      // If nothing streamed back — API was likely rate limited
      if (!hasContent) {
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: '⚠️ The AI is currently overloaded. Please wait a minute and try again.'
          }
          return updated
        })
      }

    } catch (e) {
      console.error('Chat error', e)
      setRetrieving(false)
      setMessages(prev => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last?.role === 'assistant' && !last.content) {
          updated[updated.length - 1] = {
            role: 'assistant',
            content: '⚠️ Something went wrong. Please try again in a moment.'
          }
        }
        return updated
      })
    } finally {
      setStreaming(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }
  

  return (
    <div className="flex flex-col h-full">

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
        {messages.length === 0 && (
          <div className="text-center mt-20">
            <p className="text-zinc-500">Ask anything about {topicName}</p>
            <p className="text-zinc-600 text-sm mt-1">
              I'll remember your past questions to give better answers
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div className="w-6 h-6 rounded-full bg-violet-500/20 border border-violet-800 flex items-center justify-center flex-shrink-0 mr-2 mt-1 text-xs">
                ✦
              </div>
            )}
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === 'user'
                  ? 'bg-violet-600 text-white rounded-br-sm'
                  : msg.content.startsWith('⚠️')
                  ? 'bg-zinc-900 border border-yellow-800/50 text-yellow-400 rounded-bl-sm'
                  : 'bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-bl-sm'
              }`}
            >
              {msg.role === 'assistant' ? (
                <div style={{ fontSize: '13px', lineHeight: '1.7', color: msg.content.startsWith('⚠️') ? '#facc15' : '#d4d4d8' }}>
                  <ReactMarkdown
                    components={{
                      p: ({children}) => (
                        <p style={{ marginBottom: '8px' }}>{children}</p>
                      ),
                      h1: ({children}) => (
                        <h1 style={{ fontSize: '15px', fontWeight: '600', color: 'white', marginBottom: '6px', marginTop: '12px' }}>{children}</h1>
                      ),
                      h2: ({children}) => (
                        <h2 style={{ fontSize: '14px', fontWeight: '600', color: 'white', marginBottom: '6px', marginTop: '12px' }}>{children}</h2>
                      ),
                      h3: ({children}) => (
                        <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#e4e4e7', marginBottom: '4px', marginTop: '8px' }}>{children}</h3>
                      ),
                      ul: ({children}) => (
                        <ul style={{ paddingLeft: '16px', marginBottom: '8px', display: 'flex', flexDirection: 'column', gap: '3px' }}>{children}</ul>
                      ),
                      ol: ({children}) => (
                        <ol style={{ paddingLeft: '16px', marginBottom: '8px', display: 'flex', flexDirection: 'column', gap: '3px' }}>{children}</ol>
                      ),
                      li: ({children}) => (
                        <li style={{ lineHeight: '1.6', color: '#d4d4d8' }}>{children}</li>
                      ),
                      strong: ({children}) => (
                        <strong style={{ fontWeight: '600', color: 'white' }}>{children}</strong>
                      ),
                      code: ({children, className}) => className ? (
                        <pre style={{ background: '#0a0a0a', border: '1px solid #27272a', borderRadius: '8px', padding: '12px', fontSize: '12px', fontFamily: 'monospace', color: '#a78bfa', overflowX: 'auto', margin: '8px 0' }}>
                          <code>{children}</code>
                        </pre>
                      ) : (
                        <code style={{ background: '#1a1a1a', border: '1px solid #27272a', borderRadius: '4px', padding: '1px 5px', fontSize: '12px', fontFamily: 'monospace', color: '#a78bfa' }}>{children}</code>
                      ),
                      blockquote: ({children}) => (
                        <blockquote style={{ borderLeft: '2px solid #7c3aed', paddingLeft: '12px', color: '#a1a1aa', fontStyle: 'italic', marginBottom: '8px' }}>{children}</blockquote>
                      ),
                      hr: () => (
                        <hr style={{ border: 'none', borderTop: '1px solid #27272a', margin: '12px 0' }} />
                      ),
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p style={{ lineHeight: '1.6' }}>{msg.content}</p>
              )}
            </div>
          </div>
        ))}

        {/* Retrieving indicator */}
        {retrieving && (
          <div className="flex justify-start">
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl px-4 py-3 text-xs text-zinc-500 flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-violet-500 rounded-full animate-pulse" />
              searching your study history...
            </div>
          </div>
        )}
        {/* Plan change proposal */}
{pendingPlanChange && (
  <div className="flex justify-start">
    <div className="bg-zinc-900 border border-violet-800 rounded-2xl px-4 py-4 max-w-[80%]">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-5 h-5 rounded-full bg-violet-500/20 border border-violet-800 flex items-center justify-center text-xs">✦</div>
        <p className="text-violet-400 text-xs font-medium uppercase tracking-wide">Plan Adjustment</p>
      </div>

      {!pendingPlanChange.preview ? (
        // Step 1 — show reason, ask to preview
        <>
          <p className="text-zinc-300 text-xs mb-1">
            <span className="text-white font-medium">Reason:</span> {pendingPlanChange.reason}
          </p>
          <p className="text-zinc-500 text-xs mb-4">
            Your completed tasks will be preserved. Click below to preview the new plan before applying.
          </p>
          {pendingPlanChange.error && (
  <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg bg-yellow-950/30 border border-yellow-800/50">
    <span className="text-yellow-500 text-xs">⚠️</span>
    <p className="text-yellow-400 text-xs">{pendingPlanChange.error}</p>
    <button
      onClick={() => setPendingPlanChange({ ...pendingPlanChange, error: undefined })}
      className="ml-auto text-yellow-600 hover:text-yellow-400 text-xs"
    >
      ✕
    </button>
  </div>
)}
          <div className="flex gap-2">
            
            <button
              onClick={confirmPlanChange}
              disabled={applyingPlanChange}
              className="px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-xs font-medium transition-colors"
            >
              {applyingPlanChange ? 'Generating preview...' : 'Preview new plan'}
            </button>
            <button
              onClick={() => setPendingPlanChange(null)}
              className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-xs transition-colors"
            >
              Cancel
            </button>
          </div>
        </>
      ) : (
        // Step 2 — show preview, ask to confirm
        <>
          <p className="text-zinc-400 text-xs mb-3">{pendingPlanChange.summary}</p>
          <div className="flex flex-col gap-2 mb-4">
            {pendingPlanChange.preview.map((week, i) => (
              <div key={i} className="bg-zinc-800/50 rounded-lg p-2">
                <p className="text-white text-xs font-medium mb-1">
                  Week {week.week_number} — {week.focus_area}
                </p>
                <ul className="flex flex-col gap-0.5">
                  {week.tasks.map((task, j) => (
                    <li key={j} className="text-zinc-400 text-xs flex items-start gap-1">
                      <span className="text-zinc-600 flex-shrink-0">·</span>
                      {task}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
           {pendingPlanChange.error && (
  <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg bg-yellow-950/30 border border-yellow-800/50">
    <span className="text-yellow-500 text-xs">⚠️</span>
    <p className="text-yellow-400 text-xs">{pendingPlanChange.error}</p>
    <button
      onClick={() => setPendingPlanChange({ ...pendingPlanChange, error: undefined })}
      className="ml-auto text-yellow-600 hover:text-yellow-400 text-xs"
    >
      ✕
    </button>
  </div>
)}
          <div className="flex gap-2">
           
            <button
              onClick={confirmPlanChange}
              disabled={applyingPlanChange}
              className="px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-xs font-medium transition-colors"
            >
              {applyingPlanChange ? 'Applying...' : 'Apply this plan'}
            </button>
            <button
              onClick={() => setPendingPlanChange(null)}
              className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-xs transition-colors"
            >
              Cancel
            </button>
          </div>
        </>
      )}
    </div>
  </div>
)}

        <div ref={bottomRef} />
      </div>

      <SessionBrief topicId={topicId} />

      {/* Input */}
      <div className="border-t border-zinc-800 p-4 flex gap-3">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`Ask anything about ${topicName}...`}
          rows={1}
          disabled={streaming}
          className="flex-1 bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors resize-none text-sm disabled:opacity-50"
        />
        <button
          onClick={sendMessage}
          disabled={streaming || !input.trim()}
          className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 rounded-xl transition-colors text-sm font-medium"
        >
          {streaming ? '...' : 'Send'}
        </button>
      </div>

    </div>
  )
}