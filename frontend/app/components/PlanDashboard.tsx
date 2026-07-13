'use client'

import { useState } from 'react'

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

interface Props {
  plan: Plan
  onUpdateTask: (taskId: number, status: string) => void
  onTaskClick: (description: string) => void
}

export default function PlanDashboard({ plan, onUpdateTask,onTaskClick}: Props) {
  const [openWeeks, setOpenWeeks] = useState<number[]>([1])

  const allTasks = plan.weeks.flatMap(w => w.tasks)
  const doneTasks = allTasks.filter(t => t.status === 'done').length
  const progress = Math.round((doneTasks / allTasks.length) * 100)

  function toggleWeek(weekNumber: number) {
    setOpenWeeks(prev =>
      prev.includes(weekNumber)
        ? prev.filter(w => w !== weekNumber)
        : [...prev, weekNumber]
    )
  }

  return (
    <div className="p-4">
      {/* Progress */}
      <div className="mb-6">
        <h2 className="text-white font-medium mb-1">{plan.title}</h2>
        <p className="text-zinc-500 text-xs mb-3">{doneTasks}/{allTasks.length} tasks done</p>
        <div className="w-full bg-zinc-800 rounded-full h-1.5">
          <div
            className="bg-violet-500 h-1.5 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Weeks */}
      {plan.weeks.map(week => {
        const isOpen = openWeeks.includes(week.week_number)
        const weekDone = week.tasks.filter(t => t.status === 'done').length

        return (
          <div key={week.id} className="mb-2">
            {/* Week header */}
            <button
              onClick={() => toggleWeek(week.week_number)}
              className="w-full flex items-center justify-between p-3 bg-zinc-900 border border-zinc-800 rounded-xl hover:border-zinc-700 transition-colors"
            >
              <div className="flex items-center gap-2 text-left">
                <span className="text-xs text-zinc-500">Week {week.week_number}</span>
                <span className="text-zinc-300 text-sm">{week.focus_area}</span>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-xs text-zinc-600">{weekDone}/{week.tasks.length}</span>
                <span className="text-zinc-500 text-xs">{isOpen ? '▲' : '▼'}</span>
              </div>
            </button>

            {/* Tasks */}
            {isOpen && (
              <div className="mt-1 flex flex-col gap-1 pl-2">
                {week.tasks.map(task => (
                  <div
                    key={task.id}
                    className={`flex items-start gap-3 p-3 rounded-xl border transition-colors group ${
                      task.status === 'done'
                        ? 'border-zinc-800/50 opacity-60'
                        : task.status === 'struggling'
                        ? 'border-red-900/50 bg-red-950/10'
                        : 'border-zinc-800 bg-zinc-900/50'
                    }`}
                  >
                    {/* Checkbox */}
                    <button
                      onClick={() => onUpdateTask(task.id, task.status === 'done' ? 'todo' : 'done')}
                      className={`mt-0.5 w-4 h-4 rounded flex-shrink-0 border flex items-center justify-center transition-colors ${
                        task.status === 'done'
                          ? 'bg-green-600 border-green-600'
                          : 'border-zinc-600 hover:border-green-500'
                      }`}
                    >
                      {task.status === 'done' && (
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                          <path d="M2 5L4 7L8 3" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </button>

                    {/* Text + struggling */}
                    <div className="flex-1 min-w-0">
                      
                      <p
  onClick={() => onTaskClick(task.description)}
  className={`text-xs leading-relaxed cursor-pointer hover:text-violet-400 transition-colors ${
    task.status === 'done'
      ? 'line-through text-zinc-600'
      : task.status === 'struggling'
      ? 'text-red-300'
      : 'text-zinc-300'
  }`}
>
  {task.description}
</p>
                      <button
                        onClick={() => onUpdateTask(task.id, task.status === 'struggling' ? 'todo' : 'struggling')}
                        className={`mt-1.5 text-xs px-2 py-0.5 rounded-full border transition-all ${
                          task.status === 'struggling'
                            ? 'border-red-700 text-red-400 bg-red-950/30'
                            : 'border-zinc-700 text-zinc-600 opacity-0 group-hover:opacity-100 hover:text-red-400 hover:border-red-800'
                        }`}
                      >
                        {task.status === 'struggling' ? '⚠ struggling' : 'mark struggling'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}

      {/* Weak spots */}
      {allTasks.filter(t => t.status === 'struggling').length > 0 && (
        <div className="mt-4 border-t border-zinc-800 pt-4">
          <p className="text-xs text-zinc-500 mb-2">Weak spots</p>
          {allTasks.filter(t => t.status === 'struggling').map(task => (
            <div key={task.id} className="flex items-center gap-2 mb-1">
              <span className="text-red-400 text-xs">⚠</span>
              <p className="text-zinc-400 text-xs">{task.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}