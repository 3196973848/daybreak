import { FormEvent, Fragment, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { useParams } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import { TopBar } from '../components/TopBar'
import { VerificationModal } from '../components/VerificationModal'
import type { LearningSessionDTO, LearningStage, TaskDTO } from '../types'

const STAGE_ORDER: Array<{ key: LearningStage; label: string }> = [
  { key: 'diagnose', label: '诊断' },
  { key: 'explain', label: '讲解' },
  { key: 'practice', label: '练习' },
  { key: 'remediate', label: '补强' },
  { key: 'ready', label: 'ready' },
]

interface PendingSubmission {
  client_turn_id: string
  message: string
}

function messageFrom(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

function taskFromSession(session: LearningSessionDTO): TaskDTO {
  return {
    id: session.task_id,
    title: session.task_title,
    description: session.task_description,
    type: 'learn',
    scheduled_date: null,
    effort: session.estimated_hours_snapshot,
    order: 0,
    status: 'todo',
    verified: false,
    completed_at: null,
  }
}

export function LearningPage() {
  const { taskId } = useParams()
  const numericTaskId = Number(taskId)
  const routeVersion = useRef(0)
  const [session, setSession] = useState<LearningSessionDTO | null>(null)
  const [loading, setLoading] = useState(true)
  const [preparing, setPreparing] = useState(false)
  const [sending, setSending] = useState(false)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<PendingSubmission | null>(null)
  const [verificationTask, setVerificationTask] = useState<TaskDTO | null>(null)
  const [verificationPassed, setVerificationPassed] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    routeVersion.current += 1
    setSession(null)
    setLoading(true)
    setPreparing(false)
    setSending(false)
    setDraft('')
    setPending(null)
    setVerificationTask(null)
    setVerificationPassed(false)
    setError('')

    async function load() {
      if (!taskId || !Number.isFinite(numericTaskId)) {
        if (active) {
          setError('任务编号无效')
          setLoading(false)
        }
        return
      }

      try {
        const restored = await api.getLearningSession(numericTaskId)
        if (active) setSession(restored)
      } catch (loadError) {
        if (!active) return
        if (!(loadError instanceof ApiError) || loadError.status !== 404) {
          if (active) setError(messageFrom(loadError, '加载学习记录失败'))
          return
        }

        if (active) setPreparing(true)
        try {
          const started = await api.startLearningSession(numericTaskId)
          if (active) setSession(started)
        } catch (startError) {
          if (active) setError(messageFrom(startError, '创建学习会话失败'))
        } finally {
          if (active) setPreparing(false)
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [numericTaskId, taskId])

  async function send(body: PendingSubmission) {
    const version = routeVersion.current
    setPending(body)
    setSending(true)
    setError('')
    try {
      const updated = await api.sendLearningTurn(numericTaskId, body)
      if (routeVersion.current !== version) return
      setSession(updated)
      setDraft('')
      setPending(null)
    } catch (sendError) {
      if (routeVersion.current === version) {
        setError(messageFrom(sendError, '发送失败'))
      }
    } finally {
      if (routeVersion.current === version) setSending(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (loading || sending || pending || !draft.trim()) return
    void send({ client_turn_id: crypto.randomUUID(), message: draft })
  }

  const liveStatus = preparing
    ? '导师正在准备诊断问题'
    : sending
      ? '导师正在思考'
      : loading
        ? '正在加载学习记录'
        : ''

  const stageIndex = session
    ? STAGE_ORDER.findIndex((item) => item.key === session.stage)
    : -1

  return (
    <>
      <TopBar
        title={session?.task_title ?? '导师学习'}
        backTo={session ? `/goals/${session.goal_id}/daily` : undefined}
      />
      <div className="page learning-page">
        {liveStatus && (
          <p className="learning-live-status" aria-live="polite">{liveStatus}</p>
        )}
        {error && !session && <p className="error-text" role="alert">{error}</p>}

        {session && (
          <>
            <header className="learning-header">
              <p className="learning-eyebrow">AI 导师</p>
              <h1>{session.task_title}</h1>
              {session.task_description && <p>{session.task_description}</p>}
              <div className="stage" aria-label="学习阶段">
                {STAGE_ORDER.map((item, index) => (
                  <Fragment key={item.key}>
                    {index > 0 && <span className="stage-conn" />}
                    <span className={`stage-node ${index <= stageIndex ? 'on' : ''}`}>
                      <span className="stage-dot" />
                      {item.label}
                    </span>
                  </Fragment>
                ))}
              </div>
            </header>

            <div className="learning-layout">
              <aside className="card learning-status-card" aria-label="学习状态">
                <h2>学习状态</h2>
                <dl className="learning-status-summary">
                  <div>
                    <dt>预计时长</dt>
                    <dd>{session.estimated_hours_snapshot} 小时</dd>
                  </div>
                </dl>

                <section className="learning-points">
                  <h3>已掌握</h3>
                  {session.covered_points.length > 0 ? (
                    <ul>{session.covered_points.map((point) => <li key={point}>{point}</li>)}</ul>
                  ) : <p>尚未记录</p>}
                </section>

                <section className="learning-points learning-weak-points">
                  <h3>待加强</h3>
                  {session.weak_points.length > 0 ? (
                    <ul>{session.weak_points.map((point) => <li key={point}>{point}</li>)}</ul>
                  ) : <p>暂未发现</p>}
                </section>

                <div className="learning-verify">
                  {session.ready_for_verification && !verificationPassed && (
                    <p className="learning-ready">建议开始检验</p>
                  )}
                  <button
                    className="btn"
                    disabled={verificationPassed}
                    onClick={() => setVerificationTask(taskFromSession(session))}
                  >
                    {verificationPassed ? '检验已通过' : '开始检验'}
                  </button>
                </div>
              </aside>

              <main className="card learning-chat" aria-label="导师对话">
                <div className="learning-turns">
                  {session.turns.map((turn) => (
                    <article className="learning-turn" key={turn.id}>
                      {turn.user_message !== null && (
                        <div className="learning-message learning-user-message">
                          <span className="learning-message-label">你</span>
                          <p>{turn.user_message}</p>
                        </div>
                      )}
                      <div className="learning-message learning-assistant-message">
                        <span className="learning-message-label">导师</span>
                        <div className="learning-markdown">
                          <ReactMarkdown skipHtml>{turn.assistant_message}</ReactMarkdown>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>

                <form className="learning-composer" onSubmit={submit}>
                  <label htmlFor="learning-reply">回复导师</label>
                  <textarea
                    id="learning-reply"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    disabled={loading || sending || pending !== null}
                    placeholder="写下你的理解或问题…"
                    rows={4}
                  />
                  {error && <p className="error-text" role="alert">{error}</p>}
                  <div className="learning-composer-actions">
                    {pending && error && (
                      <button
                        className="btn-ghost learning-retry"
                        type="button"
                        disabled={sending}
                        onClick={() => void send(pending)}
                      >
                        重试
                      </button>
                    )}
                    <button
                      className="btn"
                      type="submit"
                      disabled={loading || sending || pending !== null || !draft.trim()}
                    >
                      {sending ? '发送中' : '发送'}
                    </button>
                  </div>
                </form>
              </main>
            </div>
          </>
        )}

        {verificationTask && (
          <VerificationModal
            task={verificationTask}
            onClose={() => setVerificationTask(null)}
            onVerified={(result) => {
              if (result.passed) setVerificationPassed(true)
            }}
          />
        )}
      </div>
    </>
  )
}
