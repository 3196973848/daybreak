import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { DurationUnit } from '../api/client'
import type { GoalDTO } from '../types'
import { GoalList } from '../components/GoalList'
import { TopBar } from '../components/TopBar'
import { useI18n } from '../i18n'
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
  const { t } = useI18n()
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
      setDurationError(t('durationError'))
      return
    }
    setDurationError('')
    const parsedDailyHours = Number(dailyHours)
    if (
      !Number.isFinite(parsedDailyHours)
      || parsedDailyHours <= 0
      || !Number.isInteger(parsedDailyHours * 2)
    ) {
      setDailyHoursError(t('dailyHoursError'))
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
        setError(t('capacityError', {
          required: detail.required_hours,
          available: detail.available_hours,
          days: detail.minimum_days,
        }))
      } else {
        setError(err instanceof Error ? err.message : t('genericError'))
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
            <span> · {t('today')}</span>
          </div>
          <p className="eyebrow">{t('homeEyebrow')}</p>
          <h1 className="hero-title" style={{ marginTop: 10 }}>{t('homeTitle')}</h1>
          <p className="hero-sub">{t('homeSub')}</p>
        </header>

        <form className="card form-card" onSubmit={onSubmit} noValidate>
          <div className="field">
            <label htmlFor="goal-title" className="field-label">{t('goalTitle')}</label>
            <input
              id="goal-title"
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t('goalTitlePlaceholder')}
              autoFocus
            />
          </div>

          <div className="field">
            <label htmlFor="goal-desc" className="field-label">{t('goalDesc')}</label>
            <textarea
              id="goal-desc"
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('goalDescPlaceholder')}
            />
          </div>

          <div className="field">
            <label htmlFor="duration-value" className="field-label">{t('durationLabel')}</label>
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
              <label className="sr-only" htmlFor="duration-unit">{t('timeUnit')}</label>
              <select
                id="duration-unit"
                className="input"
                value={durationUnit}
                onChange={(e) => setDurationUnit(e.target.value as DurationUnit)}
              >
                <option value="day">{t('unitDay')}</option>
                <option value="week">{t('unitWeek')}</option>
                <option value="month">{t('unitMonth')}</option>
              </select>
            </div>
            <p className="field-help">{t('durationHelp')}</p>
            {durationError && (
              <p id="duration-error" role="alert" className="error-text">
                {durationError}
              </p>
            )}
          </div>

          <div className="field">
            <label htmlFor="daily-hours" className="field-label">{t('dailyHoursLabel')}</label>
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
            <p className="field-help">{t('dailyHoursHelp')}</p>
            {dailyHoursError && (
              <p id="daily-hours-error" role="alert" className="error-text">
                {dailyHoursError}
              </p>
            )}
          </div>

          {error && <p role="alert" className="error-text">{error}</p>}

          <button className="btn btn-block" disabled={loading}>
            {loading ? t('generating') : t('generate')}
          </button>
        </form>

        <GoalList
          goals={goals}
          onDelete={async (id) => {
            try {
              await api.deleteGoal(id)
              void loadGoals()
            } catch (e) {
              setError(e instanceof Error ? e.message : t('deleteFailed'))
            }
          }}
        />
      </div>
    </>
  )
}
