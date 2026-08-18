import { FormEvent, Fragment, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { useParams } from 'react-router-dom'

import { api, ApiError } from '../api/client'
import { TopBar } from '../components/TopBar'
import { VerificationModal } from '../components/VerificationModal'
import { useI18n } from '../i18n'
import type { LearningSessionDTO, LearningStage, TaskDTO } from '../types'

const STAGE_KEYS: Array<{ key: LearningStage; labelKey: string }> = [
  { key: 'diagnose', labelKey: 'stageDiagnose' },
  { key: 'explain', labelKey: 'stageExplain' },
  { key: 'practice', labelKey: 'stagePractice' },
  { key: 'remediate', labelKey: 'stageRemediate' },
  { key: 'ready', labelKey: 'stageReady' },
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
  const { t } = useI18n()
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
  const [models, setModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState('')
  const [streamingText, setStreamingText] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    api.getModels()
      .then((info) => {
        if (!active) return
        setModels(info.models)
        const saved = localStorage.getItem('planagent_model')
        setSelectedModel(saved && info.models.includes(saved) ? saved : info.default)
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [])

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
    setStreamingText('')
    setError('')

    async function load() {
      if (!taskId || !Number.isFinite(numericTaskId)) {
        if (active) {
          setError(t('invalidTask'))
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
          if (active) setError(messageFrom(loadError, t('loadSessionFailed')))
          return
        }

        if (active) setPreparing(true)
        try {
          const started = await api.startLearningSession(numericTaskId)
          if (active) setSession(started)
        } catch (startError) {
          if (active) setError(messageFrom(startError, t('createSessionFailed')))
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
  }, [numericTaskId, taskId, t])

  async function send(body: PendingSubmission) {
    const version = routeVersion.current
    setPending(body)
    setSending(true)
    setStreamingText('')
    setError('')
    try {
      await api.streamTutorTurn(
        numericTaskId,
        {
          client_turn_id: body.client_turn_id,
          message: body.message,
          model: selectedModel || undefined,
        },
        {
          onReply: (text) => {
            if (routeVersion.current === version) setStreamingText((prev) => prev + text)
          },
          onDone: (updated) => {
            if (routeVersion.current !== version) return
            setSession(updated)
            setDraft('')
            setPending(null)
            setStreamingText('')
          },
          onError: (message) => {
            if (routeVersion.current === version) setError(message)
          },
        },
      )
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
    ? t('livePreparing')
    : sending
      ? t('liveThinking')
      : loading
        ? t('liveLoading')
        : ''

  const stageIndex = session
    ? STAGE_KEYS.findIndex((item) => item.key === session.stage)
    : -1

  return (
    <>
      <TopBar
        title={session?.task_title ?? t('tutorSessionTitle')}
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
              <div className="learning-header-top">
                <div>
                  <p className="learning-eyebrow">{t('tutorEyebrow')}</p>
                  <h1>{session.task_title}</h1>
                  {session.task_description && <p>{session.task_description}</p>}
                </div>
                <button
                  className="btn learning-verify-button"
                  disabled={verificationPassed}
                  onClick={() => setVerificationTask(taskFromSession(session))}
                >
                  {verificationPassed ? t('verificationPassed') : t('startVerify')}
                </button>
              </div>
              <div className="stage" aria-label={t('stageLabel')}>
                {STAGE_KEYS.map((item, index) => (
                  <Fragment key={item.key}>
                    {index > 0 && <span className="stage-conn" />}
                    <span className={`stage-node ${index <= stageIndex ? 'on' : ''}`}>
                      <span className="stage-dot" />
                      {t(item.labelKey)}
                    </span>
                  </Fragment>
                ))}
              </div>
            </header>

            <div className="learning-layout">
              <aside className="card learning-status-card" aria-label={t('learningStatus')}>
                {models.length > 0 && (
                  <div className="field learning-model-field">
                    <label className="field-label" htmlFor="tutor-model">{t('modelLabel')}</label>
                    <select
                      id="tutor-model"
                      className="input"
                      value={selectedModel}
                      onChange={(event) => {
                        const value = event.target.value
                        setSelectedModel(value)
                        localStorage.setItem('planagent_model', value)
                      }}
                    >
                      {models.map((model) => <option key={model} value={model}>{model}</option>)}
                    </select>
                  </div>
                )}
                <h2>{t('learningStatus')}</h2>
                <dl className="learning-status-summary">
                  <div>
                    <dt>{t('currentStage')}</dt>
                    <dd>{t(STAGE_KEYS.find((item) => item.key === session.stage)?.labelKey ?? session.stage)}</dd>
                  </div>
                  <div>
                    <dt>{t('estHours')}</dt>
                    <dd>{t('hoursValue', { n: session.estimated_hours_snapshot })}</dd>
                  </div>
                </dl>

                <section className="learning-points">
                  <h3>{t('covered')}</h3>
                  {session.covered_points.length > 0 ? (
                    <ul>{session.covered_points.map((point) => <li key={point}>{point}</li>)}</ul>
                  ) : <p>{t('noCovered')}</p>}
                </section>

                <section className="learning-points learning-weak-points">
                  <h3>{t('weak')}</h3>
                  {session.weak_points.length > 0 ? (
                    <ul>{session.weak_points.map((point) => <li key={point}>{point}</li>)}</ul>
                  ) : <p>{t('noWeak')}</p>}
                </section>

                {session.ready_for_verification && !verificationPassed && (
                  <p className="learning-ready">{t('readyHint')}</p>
                )}
              </aside>

              <main className="card learning-chat" aria-label={t('chatLabel')}>
                <div className="learning-turns">
                  {session.turns.map((turn) => (
                    <article className="learning-turn" key={turn.id}>
                      {turn.user_message !== null && (
                        <div className="learning-message learning-user-message">
                          <span className="learning-message-label">{t('youLabel')}</span>
                          <p>{turn.user_message}</p>
                        </div>
                      )}
                      <div className="learning-message learning-assistant-message">
                        <span className="learning-message-label">{t('tutorLabel')}</span>
                        <div className="learning-markdown">
                          <ReactMarkdown skipHtml>{turn.assistant_message}</ReactMarkdown>
                        </div>
                      </div>
                    </article>
                  ))}
                  {streamingText !== '' && (
                    <div className="learning-message learning-assistant-message">
                      <span className="learning-message-label">{t('tutorLabel')}</span>
                      <p>{streamingText}<span className="learning-stream-cursor" /></p>
                    </div>
                  )}
                </div>

                <form className="learning-composer" onSubmit={submit}>
                  <label htmlFor="learning-reply">{t('replyLabel')}</label>
                  <textarea
                    id="learning-reply"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault()
                        submit(event as unknown as FormEvent)
                      }
                    }}
                    disabled={loading || sending || pending !== null}
                    placeholder={t('replyPlaceholder')}
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
                        {t('retry')}
                      </button>
                    )}
                    <button
                      className="btn"
                      type="submit"
                      disabled={loading || sending || pending !== null || !draft.trim()}
                    >
                      {sending ? t('sending') : t('send')}
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
