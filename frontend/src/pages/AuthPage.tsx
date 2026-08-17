import { FormEvent, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { TopBar } from '../components/TopBar'


export function AuthPage() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? '/'

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!username.trim() || !password) return
    setSubmitting(true)
    setError('')
    try {
      if (mode === 'login') {
        await login(username.trim(), password)
      } else {
        await register(username.trim(), password)
      }
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <TopBar />
      <div className="auth-page">
        <div className="auth-window">
          <div className="auth-left">
            <p className="eyebrow">目标 → 每日日程</p>
            <h1 className="auth-title">每个人的计划，<br />各自独立。</h1>
            <p className="auth-sub">注册后，你的目标、计划、每日任务和 AI 导师记录只属于你自己。</p>
            <div className="auth-feature"><span className="auth-feature-dot" />目标与里程碑全程私人化</div>
            <div className="auth-feature"><span className="auth-feature-dot" />任务检验与导师对话不串号</div>
            <div className="auth-feature"><span className="auth-feature-dot" />一处账号，多设备恢复</div>
          </div>

          <div className="auth-right">
            <div className="auth-tabs">
              <button
                type="button"
                className={`auth-tab ${mode === 'login' ? 'on' : ''}`}
                onClick={() => setMode('login')}
              >
                登录
              </button>
              <button
                type="button"
                className={`auth-tab ${mode === 'register' ? 'on' : ''}`}
                onClick={() => setMode('register')}
              >
                注册
              </button>
            </div>

            <form onSubmit={submit}>
              <div className="field">
                <label className="field-label" htmlFor="auth-username">用户名</label>
                <input
                  id="auth-username"
                  className="input"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="3-32 位字母、数字、中文或下划线"
                  autoComplete="username"
                />
              </div>
              <div className="field" style={{ marginTop: 16 }}>
                <label className="field-label" htmlFor="auth-password">密码</label>
                <input
                  id="auth-password"
                  className="input"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="至少 8 位"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
                <p className="field-help">{mode === 'login' ? '登录已有账号' : '注册后自动登录'}</p>
              </div>

              {error && <p className="error-text" role="alert" style={{ marginTop: 12 }}>{error}</p>}

              <button className="btn btn-block" disabled={submitting} style={{ marginTop: 20 }}>
                {submitting
                  ? (mode === 'login' ? '登录中…' : '注册中…')
                  : (mode === 'login' ? '登录账号' : '注册账号')}
              </button>
            </form>

            <p className="auth-foot">
              {mode === 'login' ? '还没有账号？' : '已有账号？'}
              <button
                type="button"
                className="auth-switch"
                onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
              >
                {mode === 'login' ? '切换注册' : '切换登录'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </>
  )
}
