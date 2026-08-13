import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO } from '../types'
import { GoalList } from '../components/GoalList'

export function GoalInput() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [targetDate, setTargetDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [goals, setGoals] = useState<GoalDTO[]>([])

  const loadGoals = () => api.listGoals().then(setGoals).catch(() => setGoals([]))
  useEffect(() => { void loadGoals() }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    setLoading(true)
    setError('')
    try {
      const goal = await api.createGoal({
        title: title.trim(),
        description: description.trim(),
        target_date: targetDate || null,
      })
      navigate(`/goals/${goal.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 560, margin: '40px auto', padding: '0 16px' }}>
      <h1 style={{ fontSize: 24 }}>PlanAgent</h1>
      <p className="dim">输入一个目标，AI 会把它拆解成里程碑和每日任务。</p>

      <form className="card" style={{ padding: 20, marginTop: 16 }} onSubmit={onSubmit}>
        <label className="dim" style={{ fontSize: 13 }}>目标标题 *</label>
        <input
          className="input" style={{ marginTop: 6 }}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="例如：3个月从零学会Python编程"
        />
        <label className="dim" style={{ fontSize: 13, display: 'block', marginTop: 14 }}>补充说明(可选)</label>
        <textarea
          className="input" style={{ marginTop: 6, minHeight: 64 }}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="想达到什么程度？有什么约束？"
        />
        <label className="dim" style={{ fontSize: 13, display: 'block', marginTop: 14 }}>目标完成日期(可选)</label>
        <input
          type="date" className="input" style={{ marginTop: 6 }}
          value={targetDate}
          onChange={(e) => setTargetDate(e.target.value)}
        />
        {error && <p style={{ color: '#f87171', fontSize: 13, marginTop: 10 }}>{error}</p>}
        <button className="btn" disabled={loading} style={{ marginTop: 18 }}>
          {loading ? 'AI 正在拆解计划…' : '生成计划'}
        </button>
      </form>

      <GoalList goals={goals} onDelete={async (id) => { await api.deleteGoal(id); void loadGoals() }} />
    </div>
  )
}
