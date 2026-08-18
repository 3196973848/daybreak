import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO, MilestoneDTO } from '../types'
import { ProgressBar } from '../components/ProgressBar'
import { TopBar } from '../components/TopBar'
import { useI18n } from '../i18n'
import { IconCalendar, IconChevronDown } from '../components/icons'

const STATUS_KEY: Record<string, string> = { todo: 'notStarted', active: 'inProgress', done: 'done' }

async function downloadCalendar(goalId: number) {
  const res = await fetch(`/api/goals/${goalId}/calendar.ics`)
  if (!res.ok) return
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `planagent-${goalId}.ics`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function allTasks(plan?: GoalDTO['plan']): Array<{ status: string }> {
  return plan ? plan.milestones.flatMap((m) => m.tasks) : []
}

export function PlanOverview() {
  const { id } = useParams()
  const { t } = useI18n()
  const [goal, setGoal] = useState<GoalDTO | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    api.getGoal(Number(id)).then(setGoal).catch((e) => setError(e instanceof Error ? e.message : t('failedLoad')))
  }, [id])

  if (error) return <p className="error-text">{error}</p>
  if (!goal) return <p className="faint">{t('loading')}</p>
  if (!goal.plan) {
    return (
      <>
        <TopBar title={goal.title} backTo="/" />
        <div className="page page-narrow">
          <p className="error-text">{t('noPlan')}</p>
        </div>
      </>
    )
  }

  const tasks = allTasks(goal.plan)
  const done = tasks.filter((t) => t.status === 'done').length

  return (
    <>
      <TopBar title={goal.title} backTo="/" />
      <div className="page">
        <header className="page-head">
          <div>
            <p className="eyebrow">{t('overviewEyebrow')}</p>
            <h1 className="page-title">{goal.title}</h1>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn-ghost" onClick={() => void downloadCalendar(goal.id)}>
              <IconCalendar size={14} />
              {t('exportCalendar')}
            </button>
            <Link to={`/goals/${goal.id}/daily`} className="btn-ghost">
              <IconCalendar size={14} />
              {t('dailyTasks')}
            </Link>
          </div>
        </header>

        <div className="card" style={{ padding: 18 }}>
          <ProgressBar done={done} total={tasks.length} />
          <p className="dim" style={{ fontSize: 13, marginTop: 14 }}>
            {t('strategyLabel', { strategy: goal.plan.strategy })}
          </p>
        </div>

        <div style={{ marginTop: 22 }}>
          {goal.plan.milestones.map((m) => <MilestoneCard key={m.id} m={m} />)}
        </div>
      </div>
    </>
  )
}

function MilestoneCard({ m }: { m: MilestoneDTO }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const done = m.tasks.filter((t) => t.status === 'done').length
  const statusClass = m.status === 'done' ? 'done' : m.status === 'active' ? 'active' : ''

  return (
    <div className="card row-hover milestone">
      <button
        type="button"
        className="milestone-head"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className="milestone-index">{String(m.order).padStart(2, '0')}</span>
        <div className="milestone-main">
          <div className="milestone-title">{m.title}</div>
          <div className="milestone-meta">
            <span className={`badge ${statusClass}`}>
              <span className="badge-dot" />
              {t(STATUS_KEY[m.status] ?? m.status)}
            </span>
            {m.due_date && <span className="mono">{t('dueLabel', { date: m.due_date })}</span>}
            <span>{t('doneCount', { done, total: m.tasks.length })}</span>
          </div>
          {m.description && <p className="milestone-desc">{m.description}</p>}
        </div>
        <span className={`chevron ${open ? 'open' : ''}`}>
          <IconChevronDown size={15} />
        </span>
      </button>

      <div className={`collapse ${open ? 'open' : ''}`}>
        <div>
          <div className="task-list">
            {m.tasks.map((task) => (
              <div key={task.id} className="task-line">
                <span className={`task-check ${task.status === 'done' ? 'done' : ''}`}>
                  {task.status === 'done' ? '✓' : '○'}
                </span>
                <span className={`task-title ${task.status === 'done' ? 'done' : ''}`}>{task.title}</span>
                {task.verified && <span className="verified">{t('verified')}</span>}
                <span className="task-date">{task.scheduled_date ?? ''}</span>
              </div>
            ))}
            {m.tasks.length === 0 && (
              <p className="faint" style={{ padding: '7px 0', fontSize: 12 }}>{t('noStageTasks')}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
