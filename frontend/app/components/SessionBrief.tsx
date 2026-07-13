'use client'

import { useEffect, useState } from 'react'

const API = 'http://localhost:8000'

interface Props {
  topicId: number
}

export default function SessionBrief({ topicId }: Props) {
  const [brief, setBrief] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [dismissed, setDismissed] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
  const cacheKey = `brief_${topicId}`
  const cached = sessionStorage.getItem(cacheKey)
  if (cached) {
    setBrief(cached)
    setLoading(false)
    return
  }
  fetchBrief()
}, [topicId])


  async function fetchBrief() {
  setLoading(true)
  setError(false)
  try {
    const res = await fetch(`${API}/topics/${topicId}/brief`)
    const data = await res.json()
    if (data.error) {
      setError(true)
    } else if (data.brief) {
      setBrief(data.brief)
      // Cache it for this browser session
      sessionStorage.setItem(`brief_${topicId}`, data.brief)
    }
  } catch (e) {
    setError(true)
  } finally {
    setLoading(false)
  }
}

  if (dismissed) return null

  if (loading) return (
    <div className="mx-4 mb-2 px-4 py-3 rounded-xl border border-zinc-800 bg-zinc-900/50 flex items-center gap-2">
      <span className="w-1.5 h-1.5 bg-violet-500 rounded-full animate-pulse flex-shrink-0" />
      <p className="text-zinc-500 text-xs">Preparing your session brief...</p>
    </div>
  )

  if (error) return (
    <div className="mx-4 mb-2 px-4 py-3 rounded-xl border border-yellow-800/50 bg-yellow-950/20 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <span className="text-yellow-500 text-xs">⚠️</span>
        <p className="text-yellow-400 text-xs">Session brief unavailable — AI is overloaded. 
          <button 
            onClick={fetchBrief}
            className="ml-1 underline hover:text-yellow-300 transition-colors"
          >
            Try again
          </button>
        </p>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="text-yellow-600 hover:text-yellow-400 transition-colors text-xs flex-shrink-0"
      >
        ✕
      </button>
    </div>
  )

  if (!brief) return null

  const lines = brief.split('\n').filter(l => l.trim())

  return (
    <div className="mx-4 mb-2 rounded-xl border border-violet-900/50 bg-violet-950/20 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-6 h-6 rounded-full bg-violet-500/20 border border-violet-800 flex items-center justify-center flex-shrink-0 mt-0.5 text-xs">
            ✦
          </div>
          <div>
            <p className="text-violet-400 text-xs font-medium mb-2 uppercase tracking-wide">Session Brief</p>
            <div className="flex flex-col gap-1">
              {lines.map((line, i) => (
                <p key={i} className="text-zinc-300 text-xs leading-relaxed">{line}</p>
              ))}
            </div>
          </div>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-zinc-600 hover:text-zinc-400 transition-colors flex-shrink-0 text-xs"
        >
          ✕
        </button>
      </div>
    </div>
  )
}