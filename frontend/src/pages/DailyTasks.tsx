import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { GoalDTO, TaskDTO } from '../types'
import { Calendar } from '../components/Calendar'
import { VerificationModal } from '../components/VerificationModal'
import { TopBar } from '../components/TopBar'
import { useI18n } from '../i18n'
import { IconCheck, IconClipboard } from '../components/icons'
import { todayLocal } from '../utils/date'

const TYPE_KEY: Record<string, string> = { learn: 'typeLearn', practice: 'typePractice', project: 'typeProject' }

function toKey(iso: string | null): string {
  return iso ? iso.slice(0, 10) : 'none'
}

export function DailyTasks() {
  const { id } = useParams()
  const { t } = useI18n()
  const [goal, setGoal] = useState<GoalDTO | null>(null)
  const [selected, setSelected] = useState(todayLocal)
  const [verifyTask, setVerifyTask] = useState<TaskDTO | null>(null)
  const [learningStates, setLearningStates] = useState<Record<number, boolean>>({})
  const checkedLearning = useRef<Set<number>>(new Set())
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    api.getGoal(Number(id)).then(setGoal).catch(() => undefined)
  }, [id])

  const tasks = useMemo(() => (goal?.plan ? goal.plan.milestones.flatMap((m) => m.tasks) : []), [goal])

  useEffect(() => {
    let active = true
    for (const task of tasks) {
      if (task.type !== 'learn' || checkedLearning.current.has(task.id)) continue
      checkedLearning.current.add(task.id)
      api.getLearningSession(task.id)
        .then(() => {
          if (active) setLearningStates((states) => ({ ...states, [task.id]: true }))
        })
        .catch(() => {
          if (active) setLearningStates((states) => ({ ...states, [task.id]: false }))
        })
    }
    return () => {
      active = false
    }
  }, [tasks])

  const datesWithTasks = useMemo(
    () => new Set(tasks.map((t) => toKey(t.scheduled_date))),
    [tasks],
  )
  const leaveDates = useMemo(
    () => new Set(goal?.leave_dates || []),
    [goal],
  )
  const dayTasks = useMemo(
    () => tasks.filter((t) => toKey(t.scheduled_date) === selected).sort((a, b) => a.order - b.order),
    [tasks, selected],
  )
  const isLeaveDay = leaveDates.has(selected)

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
      setError(e instanceof Error ? e.message : t('actionFailed'))
    }
  }

  async function toggleLeave() {
    if (!goal) return
    try {
      let updated: GoalDTO
      if (isLeaveDay) {
        updated = await api.removeLeave(goal.id, selected)
      } else {
        updated = await api.addLeave(goal.id, selected)
      }
      setGoal(updated)
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败')
    }
  }

  if (!goal) return <p className="faint">{t('loading')}</p>
  if (!goal.plan) {
    return (
      <>
        <TopBar title={goal.title} backTo={`/goals/${goal.id}`} />
        <div className="page page-narrow">
          <p className="error-text">{t('noPlan')}</p>
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
            <p className="eyebrow">{t('dailyEyebrow')}</p>
            <h1 className="page-title">{goal.title}</h1>
          </div>
        </header>
        {error && <p className="error-text" style={{ marginBottom: 12 }}>{error}</p>}

        <div className="daily-layout">
          <div className="card daily-list">
            <div className="daily-list-head">
              <div className="daily-date">
                {selected} · {weekdayLabel(t, selected)}
                {isLeaveDay && <span style={{ marginLeft: 8, color: 'var(--danger)', fontSize: 12 }}>· 请假</span>}
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {(dayTasks.length > 0 || isLeaveDay) && (
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={toggleLeave}
                    style={{
                      fontSize: 12,
                      color: isLeaveDay ? 'var(--text-dim)' : 'var(--danger)',
                    }}
                  >
                    {isLeaveDay ? '取消请假' : '请假'}
                  </button>
                )}
                {dayTasks.length > 0 && <div className="daily-hint">{t('clickToComplete')}</div>}
              </div>
            </div>

            {isLeaveDay && dayTasks.length === 0 && (
              <div className="empty" style={{ color: 'var(--text-faint)' }}>
                这天已请假，任务已自动后延
              </div>
            )}

            {!isLeaveDay && dayTasks.length === 0 && (
              <div className="empty">{t('noTasksDay')}</div>
            )}

            {dayTasks.map((task) => (
              <div key={task.id} className="card row-hover task-card">
                <button
                  type="button"
                  className={`circle-dot ${task.status === 'done' ? 'done' : ''}`}
                  onClick={() => void toggle(task)}
                  aria-label={task.status === 'done' ? t('markUndone') : t('markDone')}
                >
                  {task.status === 'done' && <IconCheck size={13} />}
                </button>

                <div className="task-main">
                  <div className={`task-name ${task.status === 'done' ? 'done' : ''}`}>{task.title}</div>
                  <div className="task-meta">
                    <span className="task-type">{t(TYPE_KEY[task.type] ?? task.type)}</span>
                    <span>{t('hoursShort', { n: task.effort })}</span>
                    {task.verified && <span className="verified">{t('verified')}</span>}
                  </div>
                </div>

                <button className="btn-ghost" onClick={() => setVerifyTask(task)}>
                  <IconClipboard size={14} />
                  {t('verify')}
                </button>

                {task.type === 'learn' && (
                  <Link to={`/tasks/${task.id}/learn`} className="btn-ghost">
                    {learningStates[task.id] ? t('continueLearning') : t('startLearning')}
                  </Link>
                )}
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

function weekdayLabel(t: (key: string) => string, iso: string): string {
  const d = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return ''
  const keys = ['weekSun', 'weekMon', 'weekTue', 'weekWed', 'weekThu', 'weekFri', 'weekSat']
  return t(keys[d.getDay()])
}
