'use client'

import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'

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
}

export default function ChatWindow({ topicId, topicName, initialMessages, prefillMessage, onPrefillUsed }: Props) {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [retrieving, setRetrieving] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (prefillMessage) {
      setInput(prefillMessage)
      onPrefillUsed?.()
    }
  }, [prefillMessage])

  async function sendMessage() {
    if (!input.trim() || streaming) return

    const userMessage = input.trim()
    setInput('')

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

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'assistant',
            content: updated[updated.length - 1].content + chunk
          }
          return updated
        })
      }

    } catch (e) {
      console.error('Chat error', e)
      setRetrieving(false)
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
                  : 'bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-bl-sm'
              }`}
            >
              {msg.role === 'assistant' ? (
                <div style={{ fontSize: '13px', lineHeight: '1.7', color: '#d4d4d8' }}>
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

        <div ref={bottomRef} />
      </div>

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