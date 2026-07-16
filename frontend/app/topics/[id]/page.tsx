'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { Group as PanelGroup, Panel, Separator as PanelResizeHandle } from 'react-resizable-panels'
import PlanDashboard from '@/app/components/PlanDashboard'
import ChatWindow from '@/app/components/ChatWindow'

const API = 'http://localhost:8000'

interface Task {
  id: number
  description: string
  status: string
}

interface Week {
  id: number
  week_number: number
  focus_area: string
  tasks: Task[]
}

interface Plan {
  id: number
  title: string
  duration_weeks: number
  weeks: Week[]
}

interface Message {
  id: number
  role: string
  content: string
  created_at: string
}

interface Topic {
  id: number
  name: string
  goal: string
  messages: Message[]
  plan: Plan | null
}

export default function TopicWorkspace() {
  const params = useParams()
  const topicId = params.id as string

  const [topic, setTopic] = useState<Topic | null>(null)
  const [loading, setLoading] = useState(true)
  const [planOpen, setPlanOpen] = useState(true)
  const [prefillMessage, setPrefillMessage] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => { fetchTopic() }, [topicId])

  async function fetchTopic() {
    try {
      const res = await fetch(`${API}/topics/${topicId}`)
      const data = await res.json()
      setTopic(data)
      setRefreshKey(prev => prev + 1) 
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  async function updateTaskStatus(taskId: number, status: string) {
    await fetch(`${API}/tasks/${taskId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    })
    fetchTopic()
  }

  if (loading) return (
    <div className="h-screen bg-[#080808] flex items-center justify-center">
      <div className="flex items-center gap-2">
        <div className="w-1.5 h-1.5 bg-violet-500 rounded-full animate-bounce" />
        <p className="text-zinc-500 text-sm">Loading workspace...</p>
      </div>
    </div>
  )

  if (!topic) return (
    <div className="h-screen bg-[#080808] flex items-center justify-center">
      <p className="text-zinc-500">Topic not found</p>
    </div>
  )

  return (
    <div className="h-screen flex flex-col bg-[#080808]">

      {/* Top bar */}
      <div className="border-b border-zinc-800 px-6 py-4 flex items-center gap-4 flex-shrink-0">
        <a href="/" className="text-zinc-500 hover:text-white transition-colors text-sm flex-shrink-0">
          ← Back
        </a>
        <div className="border-l border-zinc-800 pl-4 flex-1 min-w-0">
          <h1 className="text-white font-medium">{topic.name}</h1>
          <p className="text-zinc-500 text-xs mt-0.5 truncate">{topic.goal}</p>
        </div>

      </div>

      {/* Main workspace */}
  {/* Main workspace — always keep chat mounted */}
<div className="flex flex-1 overflow-hidden">

  {/* Left — Plan, hidden with CSS not unmounted */}
  <div
    className="overflow-y-auto border-r border-zinc-800 bg-[#0a0a0a] flex-shrink-0 flex flex-col transition-all duration-200"
    style={{ width: planOpen ? '35%' : '0%', overflow: planOpen ? 'auto' : 'hidden' }}
  >
    {/* Left panel header */}
    <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 flex-shrink-0 min-w-0">
      <p className="text-zinc-400 text-xs font-medium uppercase tracking-wider whitespace-nowrap">Study Plan</p>
      <button
        onClick={() => setPlanOpen(false)}
        title="Hide plan"
        className="text-zinc-500 hover:text-white transition-colors p-1 rounded-md hover:bg-zinc-800 flex-shrink-0 ml-2"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <rect x="1" y="1" width="4" height="12" rx="1" stroke="currentColor" strokeWidth="1.2"/>
          <rect x="7" y="1" width="6" height="12" rx="1" stroke="currentColor" strokeWidth="1.2"/>
        </svg>
      </button>
    </div>

    {/* Plan content */}
    <div className="flex-1 overflow-y-auto">
      {topic.plan ? (
        <PlanDashboard 
        key={refreshKey}
        plan={topic.plan} onUpdateTask={updateTaskStatus} 
        onTaskClick={(desc) => setPrefillMessage(`Help me with this task: ${desc}`)}
        />
      ) : (
        <div className="p-6">
          <p className="text-zinc-500 text-sm">No plan yet</p>
        </div>
      )}
    </div>
  </div>

  {/* Right — Chat, always mounted */}
  <div className="flex-1 overflow-hidden relative">
    {!planOpen && (
      <button
        onClick={() => setPlanOpen(true)}
        title="Show plan"
        className="absolute top-3 left-3 z-10 flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border border-zinc-700 bg-zinc-900 text-zinc-500 hover:text-white hover:border-zinc-600 transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <rect x="1" y="1" width="4" height="12" rx="1" stroke="currentColor" strokeWidth="1.2"/>
          <rect x="7" y="1" width="6" height="12" rx="1" stroke="currentColor" strokeWidth="1.2"/>
        </svg>
        Show plan
      </button>
    )}
    <ChatWindow
      topicId={Number(topicId)}
      topicName={topic.name}
      initialMessages={topic.messages}
    prefillMessage={prefillMessage}
    onPrefillUsed={() => setPrefillMessage('')}
    onTaskUpdate={fetchTopic}
    />
  </div>

</div>

    </div>
  )
}