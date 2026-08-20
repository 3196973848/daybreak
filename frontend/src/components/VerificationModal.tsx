import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type {
  DeliverContentDTO, TaskDTO, TestContentDTO, VerificationResult,
} from '../types'
import { useI18n } from '../i18n'
import { IconX } from './icons'

export function VerificationModal({
  task: taskDto, onClose, onVerified,
}: { task: TaskDTO; onClose: () => void; onVerified?: (result: VerificationResult) => void }) {
  const { t } = useI18n()
  const mode = taskDto.type === 'learn' ? 'test' : 'deliver'
  const [recordId, setRecordId] = useState(0)
  const [content, setContent] = useState<TestContentDTO | DeliverContentDTO | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [submission, setSubmission] = useState('')
  const [generating, setGenerating] = useState(true)
  const [generationAttempt, setGenerationAttempt] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<VerificationResult | null>(null)
  const [error, setError] = useState('')
  const submissionAttempt = useRef(0)
  const task = taskDto

  useEffect(() => {
    submissionAttempt.current += 1
    setAnswers({})
    setSubmission('')
    setSubmitting(false)
    setResult(null)
    return () => { submissionAttempt.current += 1 }
  }, [task.id])

  useEffect(() => {
    let active = true
    setContent(null)
    setRecordId(0)
    setError('')
    setGenerating(true)
    api.getVerification(task.id)
      .then((start) => {
        if (!active) return
        setRecordId(start.record_id)
        setContent(start.content)
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : t('failedLoad'))
      })
      .finally(() => {
        if (active) setGenerating(false)
      })
    return () => { active = false }
  }, [generationAttempt, task.id])

  async function submit() {
    if (recordId === 0 || content === null) {
      setError(t('verificationNotReady'))
      return
    }
    const attempt = ++submissionAttempt.current
    setSubmitting(true)
    setError('')
    try {
      const body = mode === 'test'
        ? { record_id: recordId, answers }
        : { record_id: recordId, submission }
      const res = await api.submitVerification(task.id, body)
      if (submissionAttempt.current !== attempt) return
      setResult(res)
      onVerified?.(res)
    } catch (e) {
      if (submissionAttempt.current === attempt) {
        setError(e instanceof Error ? e.message : t('submitFailed'))
      }
    } finally {
      if (submissionAttempt.current === attempt) setSubmitting(false)
    }
  }

  const testContent = mode === 'test' ? content as TestContentDTO : null
  const deliverContent = mode === 'deliver' ? content as DeliverContentDTO : null
  const generationLabel = mode === 'test' ? t('generatingTest') : t('generatingCriteria')
  const generationMessage = `${generationLabel}…`

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="card modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <div className="modal-title">{t('verifyTitle', { t: task.title })}</div>
            <p className="modal-sub">
              {mode === 'test' ? t('testSub') : t('deliverSub')}
            </p>
          </div>
          <button className="btn-ghost btn-icon" onClick={onClose} aria-label={t('close')}>
            <IconX size={14} />
          </button>
        </div>

        {error && <p className="error-text" role="alert" style={{ marginBottom: 12 }}>{error}</p>}

        {result ? (
          <div>
            <div className={`result-title ${result.passed ? 'result-pass' : 'result-fail'}`}>
              {result.passed ? t('passed') : t('failed')}
            </div>
            {mode === 'test' && result.points !== undefined ? (
              <>
                <div className="verification-total">{t('totalScore', { points: result.points })}</div>
                {result.details && (
                  <ol className="verification-details">
                    {result.details.map((d) => (
                      <li key={d.id} value={d.id} data-testid={`verification-detail-${d.id}`}>
                        <div className="verification-detail-heading">
                          <strong>{t('questionNo', { n: d.id })}</strong>
                          {d.type === 'choice' ? (
                            <span>
                              {d.correct === true ? t('correct') : t('wrong')} · {t('pointsPer', { n: d.points })}
                            </span>
                          ) : (
                            <span>{t('pointsPer', { n: d.points })}</span>
                          )}
                        </div>
                        {d.type === 'choice' && d.correct_answer != null && (
                          <div className="dim">{t('correctAnswer')}：{d.correct_answer}</div>
                        )}
                        {d.feedback && <p>{d.feedback}</p>}
                      </li>
                    ))}
                  </ol>
                )}
              </>
            ) : (
              <div className="score">{t('scorePct', { score: Math.round(result.score * 100) })}</div>
            )}
            <p className="feedback">{result.feedback}</p>
            <button className="btn btn-block" style={{ marginTop: 18 }} onClick={onClose}>{t('close')}</button>
          </div>
        ) : generating ? (
          <div className="verification-loading">
            <p>{generationMessage}</p>
            <div
              className="verification-progress"
              role="progressbar"
              aria-label={generationLabel}
              aria-valuetext={t('generatingInProgress')}
            ><span /></div>
          </div>
        ) : content === null ? (
          <div className="modal-actions">
            <button className="btn-ghost" onClick={onClose}>{t('cancel')}</button>
            <button className="btn" onClick={() => setGenerationAttempt((attempt) => attempt + 1)}>
              {t('regenerate')}
            </button>
          </div>
        ) : (
          <>
            {testContent && testContent.questions.map((q) => (
              <div key={q.id} className="question">
                <p className="question-text">{q.text}</p>
                {q.type === 'choice' ? (
                  q.options.map((opt) => (
                    <label key={opt} className="option">
                      <input
                        type="radio"
                        name={`q${q.id}`}
                        checked={answers[q.id] === opt}
                        onChange={() => setAnswers({ ...answers, [q.id]: opt })}
                      />
                      {opt}
                    </label>
                  ))
                ) : (
                  <textarea
                    className="input"
                    value={answers[q.id] ?? ''}
                    onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                    placeholder={t('writeAnswer')}
                  />
                )}
              </div>
            ))}

            {deliverContent && (
              <div className="question">
                <p className="question-text">{t('acceptance')}</p>
                <p className="feedback">{deliverContent.acceptance_criteria}</p>
                <textarea
                  className="input"
                  style={{ marginTop: 10 }}
                  placeholder={t('submissionPlaceholder')}
                  value={submission}
                  onChange={(e) => setSubmission(e.target.value)}
                />
              </div>
            )}

            <div className="modal-actions">
              <button className="btn-ghost" onClick={onClose}>{t('cancel')}</button>
              <button className="btn" disabled={submitting} onClick={() => void submit()}>
                {submitting ? t('reviewing') : mode === 'test' ? t('submitTest') : t('submitDeliver')}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
