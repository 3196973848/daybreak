import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { DurationUnit } from '../api/client'
import type { GoalDTO } from '../types'
import { GoalList } from '../components/GoalList'
import { TopBar } from '../components/TopBar'

export function GoalInput() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [durationValue, setDurationValue] = useState('30')
  const [durationUnit, setDurationUnit] = useState<DurationUnit>('day')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [durationError, setDurationError] = useState('')
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
    setLoading(true)
    setError('')
    try {
      const goal = await api.createGoal({
        title: title.trim(),
        description: description.trim(),
        duration_value: parsedDuration,
        duration_unit: durationUnit,
      })
      navigate(`/goals/${goal.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <TopBar />
      <div className="page page-narrow">
        <p className="dim" style={{ marginTop: 8 }}>
          输入一个目标，AI 会把它拆解成里程碑和每日任务。
        </p>

        <form className="card" style={{ padding: 24, marginTop: 20 }} onSubmit={onSubmit} noValidate>
          <label htmlFor="goal-title" className="dim" style={{ fontSize: 13 }}>目标标题 *</label>
          <input
            id="goal-title"
            className="input" style={{ marginTop: 6 }}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="例如：3个月从零学会Python编程"
            autoFocus
          />
          <label className="dim" style={{ fontSize: 13, display: 'block', marginTop: 16 }}>补充说明(可选)</label>
          <textarea
            className="input" style={{ marginTop: 6, minHeight: 64 }}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="想达到什么程度？有什么约束？"
          />
          <label htmlFor="duration-value" className="dim" style={{ fontSize: 13, display: 'block', marginTop: 16 }}>
            预期完成时间
          </label>
          <div className="duration-row" style={{ marginTop: 6 }}>
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
          <p className="faint" style={{ fontSize: 12, margin: '6px 0 0' }}>
            任务会从今天起（包含周末）均匀安排在这段时间内。
          </p>
          {durationError && (
            <p id="duration-error" role="alert" className="error-text" style={{ marginTop: 12 }}>
              {durationError}
            </p>
          )}
          {error && <p className="error-text" style={{ marginTop: 12 }}>{error}</p>}
          <button className="btn" disabled={loading} style={{ marginTop: 20, width: '100%' }}>
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
