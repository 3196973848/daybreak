import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO, TaskDTO } from '../types'
import { Calendar } from '../components/Calendar'
import { VerificationModal } from '../components/VerificationModal'
import { TopBar } from '../components/TopBar'
import { IconCheck, IconClipboard } from '../components/icons'
import { todayLocal } from '../utils/date'

const TYPE_TEXT: Record<string, string> = { learn: '学习', practice: '实操', project: '项目' }
const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

function toKey(iso: string | null): string {
  return iso ? iso.slice(0, 10) : '未排期'
}

function weekdayOf(iso: string): string {
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '' : WEEKDAYS[d.getDay()]
}

export function DailyTasks() {
  const { id } = useParams()
  const [goal, setGoal] = useState<GoalDTO | null>(null)
  const [selected, setSelected] = useState(todayLocal)
  const [verifyTask, setVerifyTask] = useState<TaskDTO | null>(null)
  const [error, setError] = useState('')

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
    try {
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
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败')
    }
  }

  if (!goal) return <p className="faint">加载中…</p>
  if (!goal.plan) {
    return (
      <>
        <TopBar title={goal.title} backTo={`/goals/${goal.id}`} />
        <div className="page page-narrow">
          <p className="error-text">此目标未生成计划。</p>
        </div>
      </>
    )
  }

  return (
    <>
      <TopBar title={goal.title} backTo={`/goals/${goal.id}`} />
      <div className="page">
        <header className="page-head">
          <div>
            <p className="eyebrow">每日任务</p>
            <h1 className="page-title">{goal.title}</h1>
          </div>
        </header>
        {error && <p className="error-text" style={{ marginBottom: 12 }}>{error}</p>}

        <div className="daily-layout">
          <div className="card daily-list">
            <div className="daily-list-head">
              <div className="daily-date">{selected} · 周{weekdayOf(selected)}</div>
              <div className="daily-hint">点击任务左侧圆点，标记完成</div>
            </div>

            {dayTasks.length === 0 && (
              <div className="empty">这一天没有安排任务，换个日期看看</div>
            )}

            {dayTasks.map((t) => (
              <div key={t.id} className="card row-hover task-card">
                <button
                  type="button"
                  className={`circle-dot ${t.status === 'done' ? 'done' : ''}`}
                  onClick={() => void toggle(t)}
                  aria-label={t.status === 'done' ? '标记未完成' : '标记完成'}
                >
                  {t.status === 'done' && <IconCheck size={13} />}
                </button>

                <div className="task-main">
                  <div className={`task-name ${t.status === 'done' ? 'done' : ''}`}>{t.title}</div>
                  <div className="task-meta">
                    <span className="task-type">{TYPE_TEXT[t.type] ?? t.type}</span>
                    <span>约 {t.effort} 小时</span>
                    {t.verified && <span className="verified">已验证</span>}
                  </div>
                </div>

                <button className="btn-ghost" onClick={() => setVerifyTask(t)}>
                  <IconClipboard size={14} />
                  检验
                </button>
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

        {verifyTask && (
          <VerificationModal
            task={verifyTask}
            onClose={() => setVerifyTask(null)}
            onVerified={() => {
              if (id) api.getGoal(Number(id)).then(setGoal).catch(() => undefined)
            }}
          />
        )}
      </div>
    </>
  )
}
