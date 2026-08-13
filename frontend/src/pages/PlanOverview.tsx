import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO, MilestoneDTO } from '../types'
import { ProgressBar } from '../components/ProgressBar'

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

  if (error) return <p style={{ color: '#f87171' }}>{error}</p>
  if (!goal) return <p className="faint">加载中…</p>
  if (!goal.plan) {
    return (
      <div style={{ maxWidth: 560, margin: '40px auto', padding: '0 16px' }}>
        <h1 style={{ fontSize: 22 }}>{goal.title}</h1>
        <p style={{ color: '#f87171' }}>此目标未生成计划(可能生成失败)。请返回删除后重试。</p>
        <Link to="/" className="btn-ghost">‹ 返回</Link>
      </div>
    )
  }

  const tasks = allTasks(goal.plan)
  const done = tasks.filter((t) => t.status === 'done').length

  return (
    <div style={{ maxWidth: 760, margin: '40px auto', padding: '0 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ fontSize: 22 }}>{goal.title}</h1>
        <Link to={`/goals/${goal.id}/daily`} className="btn-ghost">每日任务 ›</Link>
      </div>

      <div className="card" style={{ padding: 16, marginTop: 16 }}>
        <ProgressBar done={done} total={tasks.length} />
        <p className="dim" style={{ fontSize: 13, margin: '10px 0 0' }}>策略：{goal.plan.strategy}</p>
      </div>

      <div style={{ marginTop: 20 }}>
        {goal.plan.milestones.map((m) => <MilestoneCard key={m.id} m={m} />)}
      </div>
    </div>
  )
}

function MilestoneCard({ m }: { m: MilestoneDTO }) {
  const [open, setOpen] = useState(false)
  const done = m.tasks.filter((t) => t.status === 'done').length
  return (
    <div className="card" style={{ padding: 14, marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }} onClick={() => setOpen(!open)}>
        <div>
          <span style={{ fontWeight: 600 }}>里程碑 {m.order} · {m.title}</span>
          <p className="faint" style={{ fontSize: 12, margin: '4px 0 0' }}>
            {m.description} · {done}/{m.tasks.length} 完成
          </p>
        </div>
        <span className="btn-ghost" style={{ borderRadius: 10, fontSize: 12 }}>
          {STATUS_TEXT[m.status] ?? m.status}
        </span>
      </div>
      {open && (
        <div style={{ marginTop: 10 }}>
          {m.tasks.map((t) => (
            <div key={t.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 0', fontSize: 13 }}>
              <span style={{ color: t.status === 'done' ? 'var(--text-faint)' : 'var(--text)' }}>
                {t.status === 'done' ? '☑' : '☐'}
              </span>
              <span style={{ textDecoration: t.status === 'done' ? 'line-through' : 'none', color: t.status === 'done' ? 'var(--text-faint)' : 'var(--text)' }}>
                {t.title}
              </span>
              <span className="faint">{t.scheduled_date ?? ''}</span>
              {t.verified && <span className="btn-ghost" style={{ borderRadius: 10, fontSize: 11, padding: '1px 8px' }}>已验证</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
