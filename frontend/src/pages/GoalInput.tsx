import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { DurationUnit } from '../api/client'
import type { GoalDTO } from '../types'
import { GoalList } from '../components/GoalList'
import { TopBar } from '../components/TopBar'
import { todayLocal } from '../utils/date'

interface InsufficientCapacityDetail {
  code: 'insufficient_capacity'
  required_hours: number
  available_hours: number
  minimum_days: number
}

function isInsufficientCapacityDetail(detail: unknown): detail is InsufficientCapacityDetail {
  return typeof detail === 'object'
    && detail !== null
    && 'code' in detail
    && detail.code === 'insufficient_capacity'
    && 'required_hours' in detail
    && typeof detail.required_hours === 'number'
    && 'available_hours' in detail
    && typeof detail.available_hours === 'number'
    && 'minimum_days' in detail
    && typeof detail.minimum_days === 'number'
}

export function GoalInput() {
  const navigate = useNavigate()
  const today = todayLocal()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [durationValue, setDurationValue] = useState('30')
  const [durationUnit, setDurationUnit] = useState<DurationUnit>('day')
  const [dailyHours, setDailyHours] = useState('2')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [durationError, setDurationError] = useState('')
  const [dailyHoursError, setDailyHoursError] = useState('')
  const [goals, setGoals] = useState<GoalDTO[]>([])

  const loadGoals = () => api.listGoals().then(setGoals).catch(() => setGoals([]))
  useEffect(() => { void loadGoals() }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    const parsedDuration = Number(durationValue)
    if (!Number.isInteger(parsedDuration) || parsedDuration <= 0) {
      setDurationError('预期完成时间必须是正整数')
      return
    }
    setDurationError('')
    const parsedDailyHours = Number(dailyHours)
    if (
      !Number.isFinite(parsedDailyHours)
      || parsedDailyHours <= 0
      || !Number.isInteger(parsedDailyHours * 2)
    ) {
      setDailyHoursError('每日可投入时间必须是 0.5 小时的正数倍')
      return
    }
    setDailyHoursError('')
    setLoading(true)
    setError('')
    try {
      const goal = await api.createGoal({
        title: title.trim(),
        description: description.trim(),
        duration_value: parsedDuration,
        duration_unit: durationUnit,
        daily_hours: parsedDailyHours,
      })
      navigate(`/goals/${goal.id}`)
    } catch (err) {
      if (err instanceof ApiError && isInsufficientCapacityDetail(err.detail)) {
        const detail = err.detail
        setError(
          `当前时间不足：计划约需 ${detail.required_hours} 小时，现有周期可用 ${detail.available_hours} 小时。建议至少设置 ${detail.minimum_days} 天，或提高每日投入时间。`,
        )
      } else {
        setError(err instanceof Error ? err.message : '生成失败，请重试')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <TopBar />
      <div className="page page-narrow">
        <header className="hero">
          <div className="date-hero">
            {`${today.slice(0, 4)} / ${today.slice(5, 7)} / ${today.slice(8, 10)}`}
            <span> · 今天</span>
          </div>
          <p className="eyebrow">目标 → 每日日程</p>
          <h1 className="hero-title" style={{ marginTop: 10 }}>把一个目标，变成每天的日程</h1>
          <p className="hero-sub">AI 会把它拆成里程碑和每日任务，并排出可以执行的日期。</p>
        </header>

        <form className="card form-card" onSubmit={onSubmit} noValidate>
          <div className="field">
            <label htmlFor="goal-title" className="field-label">目标标题 *</label>
            <input
              id="goal-title"
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：3个月从零学会Python编程"
              autoFocus
            />
          </div>

          <div className="field">
            <label htmlFor="goal-desc" className="field-label">补充说明（可选）</label>
            <textarea
              id="goal-desc"
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="想达到什么程度？有什么约束？"
            />
          </div>

          <div className="field">
            <label htmlFor="duration-value" className="field-label">预期完成时间</label>
            <div className="duration-row">
              <input
                id="duration-value"
                type="number"
                className="input"
                min={1}
                step={1}
                required
                value={durationValue}
                aria-invalid={durationError ? true : undefined}
                aria-describedby={durationError ? 'duration-error' : undefined}
                onChange={(e) => {
                  setDurationValue(e.target.value)
                  setDurationError('')
                }}
              />
              <label className="sr-only" htmlFor="duration-unit">时间单位</label>
              <select
                id="duration-unit"
                className="input"
                value={durationUnit}
                onChange={(e) => setDurationUnit(e.target.value as DurationUnit)}
              >
                <option value="day">天</option>
                <option value="week">周</option>
                <option value="month">月</option>
              </select>
            </div>
            <p className="field-help">任务会从今天起（包含周末）均匀安排在这段时间内。</p>
            {durationError && (
              <p id="duration-error" role="alert" className="error-text">
                {durationError}
              </p>
            )}
          </div>

          <div className="field">
            <label htmlFor="daily-hours" className="field-label">每日可投入时间</label>
            <input
              id="daily-hours"
              type="number"
              className="input"
              min={0.5}
              step={0.5}
              required
              value={dailyHours}
              aria-invalid={dailyHoursError ? true : undefined}
              aria-describedby={dailyHoursError ? 'daily-hours-error' : undefined}
              onChange={(e) => {
                setDailyHours(e.target.value)
                setDailyHoursError('')
              }}
            />
            <p className="field-help">单位：小时，支持 0.5 的倍数。</p>
            {dailyHoursError && (
              <p id="daily-hours-error" role="alert" className="error-text">
                {dailyHoursError}
              </p>
            )}
          </div>

          {error && <p role="alert" className="error-text">{error}</p>}

          <button className="btn btn-block" disabled={loading}>
            {loading ? 'AI 正在拆解计划…' : '生成计划'}
          </button>
        </form>

        <GoalList
          goals={goals}
          onDelete={async (id) => {
            try {
              await api.deleteGoal(id)
              void loadGoals()
            } catch (e) {
              setError(e instanceof Error ? e.message : '删除失败')
            }
          }}
        />
      </div>
    </>
  )
}
