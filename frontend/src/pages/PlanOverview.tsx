import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO, MilestoneDTO } from '../types'
import { ProgressBar } from '../components/ProgressBar'
import { TopBar } from '../components/TopBar'
import { useI18n } from '../i18n'
import { IconCalendar, IconChevronDown } from '../components/icons'

const STATUS_KEY: Record<string, string> = { todo: 'notStarted', active: 'inProgress', done: 'done' }

function allTasks(plan?: GoalDTO['plan']): Array<{ status: string }> {
  return plan ? plan.milestones.flatMap((m) => m.tasks) : []
}

export function PlanOverview() {
  const { id } = useParams()
  const { t } = useI18n()
  const [goal, setGoal] = useState<GoalDTO | null>(null)
  const [pace, setPace] = useState<{
    total_tasks: number; completed_tasks: number;
    planned_hours: number; actual_hours: number; deviation_pct: number;
    estimated_completion_date: string | null;
    suggestion: { type: string; message: string } | null;
  } | null>(null)
  const [error, setError] = useState('')
  const [replanLoading, setReplanLoading] = useState(false)
  const [showReplanPanel, setShowReplanPanel] = useState(false)
  const [replanHours, setReplanHours] = useState('2')
  const [replanPreview, setReplanPreview] = useState<{
    changes: { task_id: number; title: string; old_date: string | null; new_date: string | null }[]
    total_days: number
    daily_hours: number
  } | null>(null)
  const [replanRestDays, setReplanRestDays] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (!id) return
    api.getGoal(Number(id)).then(setGoal).catch((e) => setError(e instanceof Error ? e.message : t('failedLoad')))
    api.getPace(Number(id)).then(setPace).catch(() => {})
  }, [id])

  async function handleReplan() {
    if (!id) return
    setReplanLoading(true)
    try {
      const hours = parseFloat(replanHours) || undefined
      const restArr = replanRestDays.size > 0 ? Array.from(replanRestDays) : undefined
      const updated = await api.replanGoal(Number(id), hours, restArr)
      setGoal(updated)
      setShowReplanPanel(false)
      setReplanPreview(null)
      api.getPace(Number(id)).then(setPace).catch(() => {})
    } catch (e) {
      setError(e instanceof Error ? e.message : '重排失败')
    } finally {
      setReplanLoading(false)
    }
  }

  async function loadReplanPreview() {
    if (!id) return
    try {
      const hours = parseFloat(replanHours) || undefined
      const restArr = replanRestDays.size > 0 ? Array.from(replanRestDays) : undefined
      const result = await api.replanPreview(Number(id), hours, restArr)
      setReplanPreview(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : '预览失败')
    }
  }

  function copyCalendarUrl() {
    if (!goal?.feed_token) return
    const url = `${window.location.origin}/api/goals/${goal.id}/calendar.ics?token=${goal.feed_token}`
    navigator.clipboard.writeText(url).then(() => alert('日历订阅链接已复制！')).catch(() => {})
  }

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
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {tasks.length - done > 0 && (
              <button className="btn-ghost" onClick={() => setShowReplanPanel(!showReplanPanel)}>
                重新安排
              </button>
            )}
            <button className="btn-ghost" onClick={copyCalendarUrl}>订阅日历</button>
            <Link to={`/goals/${goal.id}/review`} className="btn-ghost">📊 周复盘</Link>
            <Link to={`/goals/${goal.id}/daily`} className="btn-ghost">
              <IconCalendar size={14} />
              {t('dailyTasks')}
            </Link>
          </div>
        </header>

        {/* Replan panel */}
        {showReplanPanel && (
          <div className="card" style={{ padding: 16, marginBottom: 16 }}>
            <p style={{ margin: '0 0 12px', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
              重新安排未完成任务
            </p>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--text-dim)', marginBottom: 4 }}>
                  每日学习时长（小时）
                </label>
                <input
                  type="number"
                  className="input"
                  min={0.5}
                  step={0.5}
                  value={replanHours}
                  onChange={(e) => { setReplanHours(e.target.value); setReplanPreview(null) }}
                  style={{ fontFamily: 'var(--font-mono)' }}
                />
              </div>
              <button
                className="btn-ghost"
                onClick={loadReplanPreview}
                style={{ whiteSpace: 'nowrap' }}
              >
                预览变更
              </button>
            </div>

            {/* Rest days */}
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-dim)', marginBottom: 6 }}>
                休息日（不安排任务）
              </label>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {['一', '二', '三', '四', '五', '六', '日'].map((day, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => {
                      setReplanRestDays(prev => {
                        const next = new Set(prev)
                        if (next.has(i)) next.delete(i)
                        else next.add(i)
                        return next
                      })
                      setReplanPreview(null)
                    }}
                    style={{
                      width: 32, height: 32, borderRadius: '50%',
                      background: replanRestDays.has(i) ? 'var(--danger)' : 'var(--card)',
                      border: `1px solid ${replanRestDays.has(i) ? 'var(--danger)' : 'var(--hairline)'}`,
                      color: replanRestDays.has(i) ? '#fff' : 'var(--text-dim)',
                      fontSize: 12, cursor: 'pointer', transition: 'var(--transition)',
                    }}
                  >
                    {day}
                  </button>
                ))}
              </div>
            </div>

            {replanPreview && (
              <div style={{ marginBottom: 12 }}>
                <p style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: 8 }}>
                  预计 {replanPreview.total_days} 天完成（每日 {replanPreview.daily_hours} 小时）
                </p>
                <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {replanPreview.changes.map((c) => (
                    <div key={c.task_id} style={{
                      display: 'flex', justifyContent: 'space-between', padding: '6px 0',
                      borderBottom: '1px solid var(--hairline)', fontSize: 13,
                    }}>
                      <span style={{ color: 'var(--text-dim)' }}>{c.title}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-faint)' }}>
                        {c.old_date || '未排期'} → {c.new_date || '未排期'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn" onClick={handleReplan} disabled={replanLoading} style={{ flex: 1 }}>
                {replanLoading ? '重排中…' : '确认重排'}
              </button>
              <button className="btn-ghost" onClick={() => { setShowReplanPanel(false); setReplanPreview(null) }}>
                取消
              </button>
            </div>
          </div>
        )}

        {pace?.suggestion && (
          <div className="card" style={{ padding: 14, marginBottom: 12, background: '#fef3c7', border: '1px solid #f59e0b' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong style={{ color: '#92400e' }}>📊 节奏建议</strong>
                <p style={{ margin: '4px 0 0', color: '#78350f', fontSize: 14 }}>{pace.suggestion.message}</p>
                <p style={{ margin: '4px 0 0', color: '#92400e', fontSize: 12 }}>
                  预计 {pace.planned_hours}h / 实际 {pace.actual_hours}h · 偏差 {pace.deviation_pct}%
                  {pace.estimated_completion_date && ` · 推算完成 ${pace.estimated_completion_date}`}
                </p>
              </div>
              <button className="btn-ghost" onClick={() => void handleReplan()} disabled={replanLoading} style={{ whiteSpace: 'nowrap' }}>
                应用建议
              </button>
            </div>
          </div>
        )}

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
