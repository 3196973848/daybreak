import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type {
  DeliverContentDTO, TaskDTO, TestContentDTO, VerificationResult,
} from '../types'

export function VerificationModal({
  task, onClose, onVerified,
}: { task: TaskDTO; onClose: () => void; onVerified?: (result: VerificationResult) => void }) {
  const [mode, setMode] = useState<'test' | 'deliver'>('test')
  const [recordId, setRecordId] = useState(0)
  const [content, setContent] = useState<TestContentDTO | DeliverContentDTO | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [submission, setSubmission] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<VerificationResult | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.getVerification(task.id)
      .then((start) => { setMode(start.mode); setRecordId(start.record_id); setContent(start.content) })
      .catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
  }, [task.id])

  async function submit() {
    if (recordId === 0 || content === null) {
      setError('检验内容尚未加载，无法提交')
      return
    }
    setLoading(true)
    setError('')
    try {
      const body = mode === 'test'
        ? { record_id: recordId, answers }
        : { record_id: recordId, submission }
      const res = await api.submitVerification(task.id, body)
      setResult(res)
      onVerified?.(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setLoading(false)
    }
  }

  const testContent = mode === 'test' ? content as TestContentDTO : null
  const deliverContent = mode === 'deliver' ? content as DeliverContentDTO : null

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }} onClick={onClose}>
      <div className="card" style={{ padding: 20, width: 460, maxHeight: '80vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong>检验 · {task.title}</strong>
          <button className="btn-ghost" onClick={onClose}>✕</button>
        </div>
        <p className="faint" style={{ fontSize: 12, margin: '6px 0 14px' }}>
          {mode === 'test' ? '测试模式 · 答对 70% 即通过' : '交付模式 · 提交成果描述，评审是否达标'}
        </p>

        {error && <p style={{ color: '#f87171', fontSize: 13 }}>{error}</p>}

        {result ? (
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
              {result.passed ? '✓ 检验通过' : '✗ 未通过'}
            </div>
            <div className="dim" style={{ fontSize: 13, marginBottom: 8 }}>得分：{Math.round(result.score * 100)}%</div>
            <p style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{result.feedback}</p>
            <button className="btn" style={{ marginTop: 16 }} onClick={onClose}>关闭</button>
          </div>
        ) : (
          <>
            {testContent && testContent.questions.map((q) => (
              <div key={q.id} style={{ marginBottom: 14 }}>
                <p style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px' }}>{q.text}</p>
                {q.type === 'choice' ? (
                  q.options.map((opt) => (
                    <label key={opt} style={{ display: 'block', fontSize: 13, padding: '2px 0', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name={`q${q.id}`}
                        checked={answers[q.id] === opt}
                        onChange={() => setAnswers({ ...answers, [q.id]: opt })}
                      /> {opt}
                    </label>
                  ))
                ) : (
                  <textarea
                    className="input" style={{ minHeight: 56 }}
                    value={answers[q.id] ?? ''}
                    onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                  />
                )}
              </div>
            ))}
            {deliverContent && (
              <div>
                <p style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px' }}>验收标准</p>
                <p className="dim" style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{deliverContent.acceptance_criteria}</p>
                <textarea
                  className="input" style={{ minHeight: 80, marginTop: 10 }}
                  placeholder="填写你的实现成果 / 代码链接 / 说明……"
                  value={submission}
                  onChange={(e) => setSubmission(e.target.value)}
                />
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <button className="btn-ghost" onClick={onClose}>取消</button>
              <button className="btn" disabled={loading} onClick={() => void submit()}>
                {loading ? 'AI 评审中…' : mode === 'test' ? '提交检验' : '提交评审'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
