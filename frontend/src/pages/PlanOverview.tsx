import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO, MilestoneDTO } from '../types'
import { ProgressBar } from '../components/ProgressBar'
import { TopBar } from '../components/TopBar'
import { IconCalendar, IconChevronDown } from '../components/icons'

const STATUS_TEXT: Record<string, string> = { todo: '未开始', active: '进行中', done: '已完成' }

function allTasks(plan?: GoalDTO['plan']): Array<{ status: string }> {
  return plan ? plan.milestones.flatMap((m) => m.tasks) : []
}

export function PlanOverview() {
  const { id } = useParams()
  const [goal, setGoal] = useState<GoalDTO | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    api.getGoal(Number(id)).then(setGoal).catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
  }, [id])

  if (error) return <p className="error-text">{error}</p>
  if (!goal) return <p className="faint">加载中…</p>
  if (!goal.plan) {
    return (
      <>
        <TopBar title={goal.title} backTo="/" />
        <div className="page page-narrow">
          <p className="error-text">此目标未生成计划（可能生成失败），请返回删除后重试。</p>
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
            <p className="eyebrow">计划总览</p>
            <h1 className="page-title">{goal.title}</h1>
          </div>
          <Link to={`/goals/${goal.id}/daily`} className="btn-ghost">
            <IconCalendar size={14} />
            每日任务
          </Link>
        </header>

        <div className="card" style={{ padding: 18 }}>
          <ProgressBar done={done} total={tasks.length} />
          <p className="dim" style={{ fontSize: 13, marginTop: 14 }}>策略：{goal.plan.strategy}</p>
        </div>

        <div style={{ marginTop: 22 }}>
          {goal.plan.milestones.map((m) => <MilestoneCard key={m.id} m={m} />)}
        </div>
      </div>
    </>
  )
}

function MilestoneCard({ m }: { m: MilestoneDTO }) {
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
              {STATUS_TEXT[m.status] ?? m.status}
            </span>
            {m.due_date && <span className="mono">截止 {m.due_date}</span>}
            <span>{done}/{m.tasks.length} 完成</span>
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
            {m.tasks.map((t) => (
              <div key={t.id} className="task-line">
                <span className={`task-check ${t.status === 'done' ? 'done' : ''}`}>
                  {t.status === 'done' ? '✓' : '○'}
                </span>
                <span className={`task-title ${t.status === 'done' ? 'done' : ''}`}>{t.title}</span>
                {t.verified && <span className="verified">已验证</span>}
                <span className="task-date">{t.scheduled_date ?? ''}</span>
              </div>
            ))}
            {m.tasks.length === 0 && (
              <p className="faint" style={{ padding: '7px 0', fontSize: 12 }}>此阶段暂无任务</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
