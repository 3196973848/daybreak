import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO } from '../types'
import { TopBar } from '../components/TopBar'

interface ReviewData {
  year: number; week: number
  start_date: string; end_date: string
  total_planned: number; total_completed: number; completion_rate: number
  total_actual_minutes: number
  verification_count: number; verified_count: number; verification_rate: number
  daily: { date: string; weekday: string; planned_tasks: number; completed_tasks: number; actual_minutes: number }[]
  conclusion: string
}

export function ReviewPage() {
  const { id } = useParams()
  const [goal, setGoal] = useState<GoalDTO | null>(null)
  const [review, setReview] = useState<ReviewData | null>(null)
  const [week, setWeek] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    api.getGoal(Number(id)).then(setGoal).catch(() => {})
  }, [id])

  useEffect(() => {
    if (!id) return
    api.getReview(Number(id), week || undefined).then(setReview).catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
  }, [id, week])

  function getCurrentWeek() {
    const now = new Date()
    const start = new Date(now)
    start.setDate(now.getDate() - now.getDay() + 1)
    const year = start.getFullYear()
    const weekNum = Math.ceil(((start.getTime() - new Date(year, 0, 1).getTime()) / 86400000 + 1) / 7)
    return `${year}-${String(weekNum).padStart(2, '0')}`
  }

  function formatMinutes(minutes: number) {
    if (minutes < 60) return `${minutes}分钟`
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    return mins > 0 ? `${hours}小时${mins}分` : `${hours}小时`
  }

  if (error) return <p className="error-text">{error}</p>
  if (!goal) return <p className="faint">加载中…</p>

  return (
    <>
      <TopBar title={`${goal.title} - 周复盘`} backTo={`/goals/${goal.id}`} />
      <div className="page">
        <header className="page-head">
          <div>
            <p className="eyebrow">周复盘</p>
            <h1 className="page-title">{goal.title}</h1>
          </div>
          <input type="week" className="input" value={week || getCurrentWeek()} onChange={(e) => setWeek(e.target.value)} style={{ width: 180 }} />
        </header>

        {review && (
          <>
            <div className="card" style={{ padding: 18, marginBottom: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, textAlign: 'center' }}>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 'bold', color: '#3b82f6' }}>{review.completion_rate}%</div>
                  <div style={{ fontSize: 12, color: '#666' }}>完成率</div>
                </div>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 'bold', color: '#10b981' }}>{review.total_completed}/{review.total_planned}</div>
                  <div style={{ fontSize: 12, color: '#666' }}>任务完成</div>
                </div>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 'bold', color: '#f59e0b' }}>{formatMinutes(review.total_actual_minutes)}</div>
                  <div style={{ fontSize: 12, color: '#666' }}>实际用时</div>
                </div>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 'bold', color: '#8b5cf6' }}>{review.verification_rate}%</div>
                  <div style={{ fontSize: 12, color: '#666' }}>检验通过率</div>
                </div>
              </div>
            </div>

            <div className="card" style={{ padding: 14, marginBottom: 16, background: '#f0f9ff', border: '1px solid #bae6fd' }}>
              <p style={{ margin: 0, color: '#0369a1' }}>📊 {review.conclusion}</p>
            </div>

            <div className="card" style={{ padding: 18 }}>
              <h3 style={{ marginBottom: 12 }}>每日详情</h3>
              <div style={{ display: 'grid', gap: 8 }}>
                {review.daily.map((day) => (
                  <div key={day.date} style={{
                    display: 'grid', gridTemplateColumns: '100px 1fr 80px 80px', gap: 8,
                    padding: '8px 12px', background: day.completed_tasks > 0 ? '#f0fdf4' : '#f9fafb', borderRadius: 6, alignItems: 'center',
                  }}>
                    <div>
                      <div style={{ fontWeight: 500 }}>{day.weekday}</div>
                      <div style={{ fontSize: 12, color: '#666' }}>{day.date.slice(5)}</div>
                    </div>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {Array.from({ length: day.planned_tasks }).map((_, i) => (
                        <div key={i} style={{ width: 20, height: 20, borderRadius: 4, background: i < day.completed_tasks ? '#10b981' : '#e5e7eb' }} />
                      ))}
                    </div>
                    <div style={{ fontSize: 13, color: '#666' }}>{day.completed_tasks}/{day.planned_tasks}</div>
                    <div style={{ fontSize: 13, color: '#666' }}>{day.actual_minutes > 0 ? formatMinutes(day.actual_minutes) : '-'}</div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </>
  )
}
