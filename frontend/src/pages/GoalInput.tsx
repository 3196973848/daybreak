import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO } from '../types'
import { GoalList } from '../components/GoalList'
import { TopBar } from '../components/TopBar'
import { useI18n } from '../i18n'
import { todayLocal } from '../utils/date'

interface PreviewData {
  strategy: string
  assumptions: string[]
  milestones: { title: string; description: string; order: number; tasks: { title: string }[] }[]
  total_hours: number
}

export function GoalInput() {
  const navigate = useNavigate()
  const { t } = useI18n()
  const today = todayLocal()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [dailyHours, setDailyHours] = useState('2')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [goals, setGoals] = useState<GoalDTO[]>([])

  // Preview state
  const [preview, setPreview] = useState<PreviewData | null>(null)
  const [rejectedAssumptions, setRejectedAssumptions] = useState<Set<number>>(new Set())
  const [restDays, setRestDays] = useState<Set<number>>(new Set())

  const loadGoals = () => api.listGoals().then(setGoals).catch(() => setGoals([]))
  useEffect(() => { void loadGoals() }, [])

  function toggleAssumption(index: number) {
    setRejectedAssumptions((prev) => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  async function onPreview(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    const parsedDailyHours = Number(dailyHours)
    if (!Number.isFinite(parsedDailyHours) || parsedDailyHours <= 0) {
      setError('请输入有效的每日时间')
      return
    }
    setLoading(true)
    setError('')
    try {
      const result = await api.previewGoal({
        title: title.trim(),
        description: description.trim(),
        daily_hours: parsedDailyHours,
        rest_days: restDays.size > 0 ? Array.from(restDays) : undefined,
      })
      setPreview(result)
      setRejectedAssumptions(new Set())
    } catch (err) {
      setError(err instanceof Error ? err.message : t('genericError'))
    } finally {
      setLoading(false)
    }
  }

  async function onCreateGoal() {
    if (!title.trim()) return
    const parsedDailyHours = Number(dailyHours)
    if (!Number.isFinite(parsedDailyHours) || parsedDailyHours <= 0) {
      setError('请输入有效的每日时间')
      return
    }
    setLoading(true)
    setError('')
    try {
      const rejected = preview?.assumptions
        ? preview.assumptions.filter((_, i) => rejectedAssumptions.has(i))
        : []
      const goal = await api.createGoal({
        title: title.trim(),
        description: description.trim(),
        daily_hours: parsedDailyHours,
        rejected_assumptions: rejected.length > 0 ? rejected : undefined,
        rest_days: restDays.size > 0 ? Array.from(restDays) : undefined,
      })
      navigate(`/goals/${goal.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('genericError'))
    } finally {
      setLoading(false)
    }
  }

  function resetForm() {
    setPreview(null)
    setRejectedAssumptions(new Set())
    setError('')
  }

  return (
    <>
      <TopBar />
      <div className="page page-narrow">
        <header className="hero">
          <div className="date-hero">
            {`${today.slice(0, 4)} / ${today.slice(5, 7)} / ${today.slice(8, 10)}`}
            <span> · {t('today')}</span>
          </div>
          <p className="eyebrow">{t('homeEyebrow')}</p>
          <h1 className="hero-title" style={{ marginTop: 10 }}>{t('homeTitle')}</h1>
          <p className="hero-sub">{t('homeSub')}</p>
        </header>

        {!preview ? (
          <form className="card form-card" onSubmit={onPreview} noValidate>
            <div className="field">
              <label htmlFor="goal-title" className="field-label">{t('goalTitle')}</label>
              <input id="goal-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t('goalTitlePlaceholder')} autoFocus />
            </div>
            <div className="field">
              <label htmlFor="goal-desc" className="field-label">{t('goalDesc')}</label>
              <textarea id="goal-desc" className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder={t('goalDescPlaceholder')} />
            </div>
            <div className="field">
              <label htmlFor="daily-hours" className="field-label">每日投入时间（小时）</label>
              <input id="daily-hours" type="number" className="input" min={0.5} step={0.5} required value={dailyHours} onChange={(e) => setDailyHours(e.target.value)} />
              <p className="field-help">系统会根据目标自动安排每天的任务</p>
            </div>
            {error && <p role="alert" className="error-text">{error}</p>}
            <button className="btn btn-block" disabled={loading}>
              {loading ? 'AI 正在分析…' : '预览计划'}
            </button>
          </form>
        ) : (
          <div className="card form-card" style={{ padding: 0, overflow: 'hidden' }}>
            {/* Strategy banner */}
            <div style={{
              padding: '20px 24px',
              background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
              borderBottom: '1px solid var(--hairline)',
            }}>
              <p style={{ margin: 0, fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
                Strategy
              </p>
              <p style={{ margin: '6px 0 0', fontSize: 15, lineHeight: 1.6, color: 'var(--text)', fontFamily: 'var(--font-display)' }}>
                {preview.strategy}
              </p>
            </div>

            <div style={{ padding: '20px 24px' }}>
              {/* Stats */}
              <div style={{
                display: 'flex', gap: 16, marginBottom: 20, padding: '12px 14px',
                background: 'var(--card)', borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--hairline)',
              }}>
                <div style={{ flex: 1, textAlign: 'center' }}>
                  <div style={{ fontSize: 20, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text)' }}>
                    {preview.total_hours}h
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>总工时</div>
                </div>
                <div style={{ width: 1, background: 'var(--hairline)' }} />
                <div style={{ flex: 1, textAlign: 'center' }}>
                  <div style={{ fontSize: 20, fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--text)' }}>
                    {preview.milestones.reduce((s, m) => s + m.tasks.length, 0)}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>任务数</div>
                </div>
              </div>

              {/* Assumptions */}
              {preview.assumptions.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                  <p style={{ margin: '0 0 10px', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
                    Assumptions · 假设
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {preview.assumptions.map((a, i) => {
                      const rejected = rejectedAssumptions.has(i)
                      return (
                        <label key={i} style={{
                          display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 14px',
                          borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                          background: rejected ? 'rgba(248, 113, 113, 0.06)' : 'var(--card)',
                          border: `1px solid ${rejected ? 'rgba(248, 113, 113, 0.25)' : 'var(--hairline)'}`,
                          transition: 'var(--transition)',
                        }}>
                          <input
                            type="checkbox"
                            checked={!rejected}
                            onChange={() => toggleAssumption(i)}
                            style={{ marginTop: 3, accentColor: 'var(--text)' }}
                          />
                          <span style={{
                            fontSize: 14, lineHeight: 1.5,
                            textDecoration: rejected ? 'line-through' : 'none',
                            color: rejected ? 'var(--text-faint)' : 'var(--text-dim)',
                            transition: 'var(--transition)',
                          }}>{a}</span>
                        </label>
                      )
                    })}
                  </div>
                  {rejectedAssumptions.size > 0 && (
                    <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--danger)', fontFamily: 'var(--font-mono)' }}>
                      −{rejectedAssumptions.size} 条假设将被否决，计划会据此调整
                    </p>
                  )}
                </div>
              )}

              {/* Rest days */}
              <div style={{ marginBottom: 24 }}>
                <p style={{ margin: '0 0 10px', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
                  Rest Days · 休息日
                </p>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {['周一', '周二', '周三', '周四', '周五', '周六', '周日'].map((day, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => {
                        setRestDays(prev => {
                          const next = new Set(prev)
                          if (next.has(i)) next.delete(i)
                          else next.add(i)
                          return next
                        })
                      }}
                      style={{
                        padding: '6px 12px', borderRadius: 'var(--radius-xs)',
                        background: restDays.has(i) ? 'var(--danger)' : 'var(--card)',
                        border: `1px solid ${restDays.has(i) ? 'var(--danger)' : 'var(--hairline)'}`,
                        color: restDays.has(i) ? '#fff' : 'var(--text-dim)',
                        fontSize: 13, cursor: 'pointer', transition: 'var(--transition)',
                      }}
                    >
                      {day}
                    </button>
                  ))}
                </div>
                <p style={{ margin: '6px 0 0', fontSize: 12, color: 'var(--text-faint)' }}>
                  {restDays.size === 0 ? '每天都有任务安排' : `每周休息 ${restDays.size} 天`}
                </p>
              </div>

              {/* Milestones */}
              <div>
                <p style={{ margin: '0 0 12px', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
                  Milestones · 里程碑
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {preview.milestones.map((m) => (
                    <div key={m.order} style={{
                      display: 'flex', gap: 14, padding: '12px 14px',
                      background: 'var(--card)', borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--hairline)',
                    }}>
                      <span style={{
                        flexShrink: 0, width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        borderRadius: '50%', background: 'var(--hairline)', color: 'var(--text-dim)',
                        fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 600,
                      }}>
                        {m.order}
                      </span>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text)' }}>{m.title}</div>
                        <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 2 }}>
                          {m.description && <span>{m.description} · </span>}
                          <span style={{ fontFamily: 'var(--font-mono)' }}>{m.tasks.length}</span> 个任务
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div style={{
              display: 'flex', gap: 8, padding: '16px 24px',
              borderTop: '1px solid var(--hairline)', background: 'var(--bg-soft)',
            }}>
              <button className="btn btn-block" onClick={() => onCreateGoal()} disabled={loading} style={{ flex: 1 }}>
                {loading ? '正在生成…' : '确认生成计划'}
              </button>
              <button className="btn-ghost" onClick={resetForm} disabled={loading}>重新填写</button>
            </div>

            {error && <p role="alert" className="error-text" style={{ padding: '0 24px 12px' }}>{error}</p>}
          </div>
        )}

        <GoalList goals={goals} onDelete={async (id) => { try { await api.deleteGoal(id); void loadGoals() } catch (e) { setError(e instanceof Error ? e.message : t('deleteFailed')) } }} />
      </div>
    </>
  )
}
