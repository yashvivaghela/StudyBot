'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

const API = 'http://localhost:8000'

interface Topic {
  id: number
  name: string
  goal: string
  created_at: string
  has_plan: boolean
}

export default function Home() {
  const router = useRouter()
  const [topics, setTopics] = useState<Topic[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [name, setName] = useState('')
  const [goal, setGoal] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => { fetchTopics() }, [])

  async function fetchTopics() {
    try {
      const res = await fetch(`${API}/topics`)
      const data = await res.json()
      setTopics(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate() {
    if (!name.trim() || !goal.trim()) return
    setCreating(true)
    try {
      const res = await fetch(`${API}/topics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, goal })
      })
      const topic = await res.json()
      await fetch(`${API}/topics/${topic.id}/plan`, { method: 'POST' })
      router.push(`/topics/${topic.id}`)
    } catch (e) {
      console.error(e)
      setCreating(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#080808]">

      {/* Header */}
      <div className="border-b border-zinc-800 px-8 py-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-white font-semibold text-lg tracking-tight">StudyBot</h1>

          </div>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="bg-violet-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-violet-500 transition-colors flex items-center gap-2 shadow-lg shadow-violet-500/20"
        >
          <span>+</span> New Topic
        </button>
      </div>

      {/* Content */}
      <div className="px-8 py-8 max-w-6xl mx-auto">
        {loading ? (
          <div className="flex items-center gap-2 mt-20 justify-center">
            <div className="w-1.5 h-1.5 bg-violet-500 rounded-full animate-bounce" />
            <p className="text-zinc-500 text-sm">Loading...</p>
          </div>
        ) : topics.length === 0 ? (
          <div className="text-center mt-32">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 bg-violet-500/10 border border-zinc-800">
              <span className="text-2xl">✦</span>
            </div>
            <p className="text-white font-medium mb-2">No topics yet</p>
            <p className="text-zinc-500 text-sm">Create your first study topic to get started</p>
          </div>
        ) : (
          <>
            <p className="text-zinc-500 text-xs mb-6 uppercase tracking-widest">
              Your topics — {topics.length}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {topics.map(topic => (
                <div
                  key={topic.id}
                  onClick={() => router.push(`/topics/${topic.id}`)}
                  className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 cursor-pointer group transition-all duration-200 hover:border-violet-500/50 hover:shadow-lg hover:shadow-violet-500/5"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h2 className="text-white font-medium group-hover:text-violet-400 transition-colors">
                      {topic.name}
                    </h2>
                    {topic.has_plan && (
                      <span className="text-xs px-2 py-0.5 rounded-full flex-shrink-0 ml-2 bg-violet-500/10 text-violet-400 border border-violet-900">
                        plan ready
                      </span>
                    )}
                  </div>
                  <p className="text-zinc-500 text-sm line-clamp-2 leading-relaxed">
                    {topic.goal}
                  </p>
                  <div className="mt-4 pt-3 border-t border-zinc-800 flex items-center justify-between">
                    <p className="text-zinc-600 text-xs">
                      {new Date(topic.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </p>
                    <span className="text-zinc-600 text-xs group-hover:text-violet-400 transition-colors">
                      Open →
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div
          className="fixed inset-0 flex items-center justify-center z-50 p-4 bg-black/80 backdrop-blur-sm"
        >
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 w-full max-w-md shadow-2xl">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-violet-500/10 border border-violet-600">
                <span className="text-sm">✦</span>
              </div>
              <h2 className="text-white font-semibold">New study topic</h2>
            </div>

            <div className="mb-4">
              <label className="text-zinc-500 text-xs mb-2 block uppercase tracking-wide">
                Topic name
              </label>
              <input
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. LeetCode Prep"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>

            <div className="mb-6">
              <label className="text-zinc-500 text-xs mb-2 block uppercase tracking-wide">
                Your goal
              </label>
              <textarea
                value={goal}
                onChange={e => setGoal(e.target.value)}
                placeholder="e.g. Prepare for SWE interviews in 4 weeks, focus on arrays and DP"
                rows={4}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors resize-none"
              />
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowModal(false)}
                className="flex-1 py-3 rounded-xl text-sm text-zinc-400 bg-zinc-800 border border-zinc-700 hover:border-zinc-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !name.trim() || !goal.trim()}
                className="flex-1 text-white py-3 rounded-xl text-sm font-medium bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-violet-500/20"
              >
                {creating ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-1 h-1 bg-white rounded-full animate-bounce" />
                    Generating plan...
                  </span>
                ) : 'Create & generate plan'}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}