import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO, TaskDTO } from '../types'
import { Calendar } from '../components/Calendar'
import { VerificationModal } from '../components/VerificationModal'

const TYPE_TEXT: Record<string, string> = { learn: '学习', practice: '实操', project: '项目' }

function toKey(iso: string | null): string {
  return iso ? iso.slice(0, 10) : '未排期'
}

export function DailyTasks() {
  const { id } = useParams()
  const [goal, setGoal] = useState<GoalDTO | null>(null)
  const [selected, setSelected] = useState(() => new Date().toISOString().slice(0, 10))
  const [verifyTask, setVerifyTask] = useState<TaskDTO | null>(null)

  useEffect(() => {
    if (!id) return
    api.getGoal(Number(id)).then(setGoal).catch(() => undefined)
  }, [id])

  const tasks = useMemo(() => (goal?.plan ? goal.plan.milestones.flatMap((m) => m.tasks) : []), [goal])
  const datesWithTasks = useMemo(
    () => new Set(tasks.map((t) => toKey(t.scheduled_date))),
    [tasks],
  )
  const dayTasks = useMemo(
    () => tasks.filter((t) => toKey(t.scheduled_date) === selected).sort((a, b) => a.order - b.order),
    [tasks, selected],
  )

  async function toggle(task: TaskDTO) {
    const updated = await api.setTaskCompleted(task.id, task.status !== 'done')
    setGoal((g) => (g ? {
      ...g,
      plan: {
        ...g.plan!,
        milestones: g.plan!.milestones.map((m) => ({
          ...m,
          tasks: m.tasks.map((t) => (t.id === updated.id ? updated : t)),
        })),
      },
    } : g))
  }

  if (!goal || !goal.plan) return <p className="faint">加载中…</p>

  return (
    <div style={{ maxWidth: 760, margin: '40px auto', padding: '0 16px' }}>
      <Link to={`/goals/${goal.id}`} className="btn-ghost">‹ 返回总览</Link>
      <h1 style={{ fontSize: 22 }}>{goal.title}</h1>

      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', marginTop: 16, flexWrap: 'wrap' }}>
        <div className="card" style={{ padding: 16, flex: 1, minWidth: 300 }}>
          <div style={{ textAlign: 'center', marginBottom: 12 }}>
            <div style={{ fontWeight: 600 }}>{selected}</div>
            <div className="faint" style={{ fontSize: 12 }}>点击任务左侧圆点可勾选完成</div>
          </div>
          {dayTasks.length === 0 && <p className="faint" style={{ textAlign: 'center' }}>这一天没有任务</p>}
          {dayTasks.map((t) => (
            <div key={t.id} className="card" style={{ padding: '10px 12px', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
              <div
                onClick={() => void toggle(t)}
                style={{
                  width: 18, height: 18, borderRadius: '50%', flexShrink: 0, cursor: 'pointer',
                  background: t.status === 'done' ? 'var(--accent)' : 'transparent',
                  border: `2px solid ${t.status === 'done' ? 'var(--accent)' : 'var(--text-faint)'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, color: '#000',
                }}
              >
                {t.status === 'done' ? '✓' : ''}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, textDecoration: t.status === 'done' ? 'line-through' : 'none', color: t.status === 'done' ? 'var(--text-faint)' : 'var(--text)' }}>
                  {t.title}
                </div>
                <div className="faint" style={{ fontSize: 11, marginTop: 2 }}>
                  {TYPE_TEXT[t.type] ?? t.type} · 约 {t.effort} 小时
                  {t.verified ? ' · 已验证' : ''}
                </div>
              </div>
              <button className="btn-ghost" onClick={() => setVerifyTask(t)}>去检验</button>
            </div>
          ))}
        </div>

        <Calendar
          year={Number(selected.slice(0, 4))}
          month={Number(selected.slice(5, 7)) - 1}
          selected={selected}
          datesWithTasks={datesWithTasks}
          onSelect={setSelected}
        />
      </div>

      {verifyTask && <VerificationModal task={verifyTask} onClose={() => setVerifyTask(null)} />}
    </div>
  )
}
