import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import { TopBar } from '../components/TopBar'
import type { ProviderDTO, SettingsDTO } from '../types'


export function SetupPage() {
  const navigate = useNavigate()
  const [settings, setSettings] = useState<SettingsDTO | null>(null)
  const [providerId, setProviderId] = useState('deepseek')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    api.getSettings()
      .then((value) => {
        if (!active) return
        setSettings(value)
        setProviderId(value.provider)
        setModel(value.model)
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [])

  const provider = useMemo<ProviderDTO | null>(
    () => settings?.providers.find((item) => item.id === providerId) ?? null,
    [settings, providerId],
  )

  function chooseProvider(id: string) {
    setProviderId(id)
    const next = settings?.providers.find((item) => item.id === id)
    setModel(next?.models[0] ?? '')
    setBaseUrl('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!provider) return
    if (provider.requires_key && !apiKey.trim()) {
      setError('请填写 API Key')
      return
    }
    setSaving(true)
    setError('')
    try {
      await api.saveSettings({
        provider: providerId,
        api_key: apiKey.trim() || undefined,
        base_url: baseUrl.trim() || undefined,
        model: model || undefined,
      })
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (!settings) {
    return <div className="page"><p className="faint">加载中…</p></div>
  }

  return (
    <>
      <TopBar />
      <div className="page page-narrow">
        <header className="hero">
          <p className="eyebrow">首次设置</p>
          <h1 className="hero-title">选择你的 AI 提供方</h1>
          <p className="hero-sub">填入 API Key 后即可开始；Key 只保存在本机配置文件中。</p>
        </header>

        <form className="card form-card" onSubmit={submit}>
          <div className="setup-providers">
            {settings.providers.map((item) => (
              <button
                type="button"
                key={item.id}
                className={`setup-provider ${item.id === providerId ? 'on' : ''}`}
                onClick={() => chooseProvider(item.id)}
              >
                <strong>{item.name}</strong>
                <span>{item.requires_key ? '需要 API Key' : '本地运行，无需 Key'}</span>
              </button>
            ))}
          </div>

          {provider?.requires_key && (
            <div className="field">
              <label className="field-label" htmlFor="setup-key">API Key</label>
              <input
                id="setup-key"
                className="input"
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder="sk-…"
                autoComplete="off"
              />
            </div>
          )}

          {providerId === 'custom' && (
            <div className="field">
              <label className="field-label" htmlFor="setup-base">Base URL（OpenAI 兼容）</label>
              <input
                id="setup-base"
                className="input"
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder="https://…/v1"
              />
            </div>
          )}

          <div className="field">
            <label className="field-label" htmlFor="setup-model">默认模型</label>
            <select
              id="setup-model"
              className="input"
              value={model}
              onChange={(event) => setModel(event.target.value)}
            >
              {(provider?.models ?? []).map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </div>

          {error && <p className="error-text" role="alert">{error}</p>}

          <button className="btn btn-block" disabled={saving}>
            {saving ? '保存中…' : '保存并开始'}
          </button>
        </form>
      </div>
    </>
  )
}
