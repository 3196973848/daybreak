import { FormEvent, useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import { invalidateSettingsCache } from '../auth/SetupGate'
import { TopBar } from '../components/TopBar'
import { useI18n } from '../i18n'
import type { ProviderDTO, SettingsDTO } from '../types'

const PROVIDER_ICONS: Record<string, string> = {
  deepseek: '🔮',
  openai: '✦',
  ollama: '🦙',
  anthropic: '🅰',
}

export function SetupPage() {
  const { t } = useI18n()
  const [settings, setSettings] = useState<SettingsDTO | null>(null)
  const [providerId, setProviderId] = useState('deepseek')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [customModel, setCustomModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  // Custom provider form state
  const [showAddForm, setShowAddForm] = useState(false)
  const [newName, setNewName] = useState('')
  const [newBaseUrl, setNewBaseUrl] = useState('')
  const [newApiKey, setNewApiKey] = useState('')
  const [newModels, setNewModels] = useState('')
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    let active = true
    api.getSettings()
      .then((value) => {
        if (!active) return
        setSettings(value)
        setProviderId(value.provider)
        const currentProvider = value.providers.find(p => p.id === value.provider)
        if (currentProvider && !currentProvider.models.includes(value.model)) {
          setCustomModel(value.model)
          setModel('')
        } else {
          setModel(value.model)
          setCustomModel('')
        }
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  const provider = useMemo<ProviderDTO | null>(
    () => settings?.providers.find((item) => item.id === providerId) ?? null,
    [settings, providerId],
  )

  const isCurrentProvider = providerId === settings?.provider
  const keyAlreadyConfigured = isCurrentProvider && settings?.has_api_key
  const effectiveModel = customModel.trim() || model

  function chooseProvider(id: string) {
    setProviderId(id)
    const next = settings?.providers.find((item) => item.id === id)
    if (next) {
      // Auto-fill base_url for custom providers
      if (next.is_custom && next.base_url) {
        // base_url is handled by the provider selection
      }
      if (next.models.length > 0) {
        setModel(next.models[0])
        setCustomModel('')
      } else {
        setModel('')
        setCustomModel('')
      }
      // For custom providers, pre-fill API key if available
      if (next.is_custom) {
        setApiKey('')
      }
    }
    setSaved(false)
    setError('')
  }

  function selectModel(m: string) {
    setModel(m)
    setCustomModel('')
    setSaved(false)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!provider) return
    if (provider.requires_key && !apiKey.trim() && !keyAlreadyConfigured) {
      setError(t('keyRequired'))
      return
    }
    if (!effectiveModel) {
      setError('请选择或输入一个模型名称')
      return
    }
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      await api.saveSettings({
        provider: providerId,
        api_key: apiKey.trim() || undefined,
        base_url: provider.is_custom ? provider.base_url : undefined,
        model: effectiveModel,
      })
      invalidateSettingsCache()
      setSaved(true)
      setApiKey('')
      const updated = await api.getSettings()
      setSettings(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  async function addCustomProvider(event: FormEvent) {
    event.preventDefault()
    if (!newName.trim() || !newBaseUrl.trim()) {
      setError('名称和 API 地址不能为空')
      return
    }
    setAdding(true)
    setError('')
    try {
      const updated = await api.createCustomProvider({
        name: newName.trim(),
        base_url: newBaseUrl.trim(),
        api_key: newApiKey.trim(),
        models: newModels.split(',').map(m => m.trim()).filter(Boolean),
      })
      invalidateSettingsCache()
      setSettings(updated)
      setShowAddForm(false)
      setNewName('')
      setNewBaseUrl('')
      setNewApiKey('')
      setNewModels('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加失败')
    } finally {
      setAdding(false)
    }
  }

  async function deleteCustomProvider(id: string) {
    if (!confirm('确定删除此服务商？')) return
    try {
      const updated = await api.deleteCustomProvider(id)
      invalidateSettingsCache()
      setSettings(updated)
      if (providerId === id) {
        setProviderId(updated.provider)
        setModel(updated.model)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  if (!settings) {
    return <div className="page"><p className="faint">{t('loading')}</p></div>
  }

  return (
    <>
      <TopBar />
      <div className="page page-narrow">
        <header className="hero">
          <p className="eyebrow">Settings</p>
          <h1 className="hero-title">模型配置</h1>
          <p className="hero-sub">选择 AI 服务商和模型，配置 API Key 后即可使用</p>
        </header>

        {saved && (
          <div style={{
            padding: '10px 16px', marginBottom: 16, borderRadius: 'var(--radius-sm)',
            background: 'rgba(74, 222, 128, 0.08)', border: '1px solid rgba(74, 222, 128, 0.2)',
            color: '#4ade80', fontSize: 14,
          }}>
            ✓ 配置已保存
          </div>
        )}

        <form onSubmit={submit}>
          {/* Provider selection */}
          <div style={{ marginBottom: 24 }}>
            <label style={{
              display: 'block', marginBottom: 10, fontSize: 11,
              letterSpacing: '0.08em', textTransform: 'uppercase',
              color: 'var(--text-faint)', fontFamily: 'var(--font-mono)',
            }}>
              Provider · 服务商
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
              {settings.providers.map((item) => (
                <div key={item.id} style={{ position: 'relative' }}>
                  <button
                    type="button"
                    onClick={() => chooseProvider(item.id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                      padding: '12px 14px', borderRadius: 'var(--radius-sm)',
                      background: item.id === providerId ? 'var(--card-hover)' : 'var(--card)',
                      border: `1px solid ${item.id === providerId ? 'var(--border-strong)' : 'var(--hairline)'}`,
                      cursor: 'pointer', textAlign: 'left',
                      transition: 'var(--transition)',
                    }}
                  >
                    <span style={{ fontSize: 20, flexShrink: 0 }}>{PROVIDER_ICONS[item.id] || '⚙'}</span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
                        {item.is_custom ? '自定义' : item.requires_key ? '需要 API Key' : '本地运行'}
                      </div>
                    </div>
                  </button>
                  {item.is_custom && (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); deleteCustomProvider(item.id) }}
                      title="删除"
                      style={{
                        position: 'absolute', top: 4, right: 4,
                        width: 20, height: 20, borderRadius: '50%',
                        background: 'var(--danger)', color: '#fff',
                        border: 'none', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, lineHeight: 1,
                      }}
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}

              {/* Add custom provider button */}
              <button
                type="button"
                onClick={() => setShowAddForm(!showAddForm)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  padding: '12px 14px', borderRadius: 'var(--radius-sm)',
                  background: 'var(--card)',
                  border: `1px dashed ${showAddForm ? 'var(--accent)' : 'var(--border)'}`,
                  cursor: 'pointer', color: 'var(--text-dim)', fontSize: 14,
                  transition: 'var(--transition)',
                }}
              >
                <span style={{ fontSize: 18 }}>+</span>
                添加服务商
              </button>
            </div>
          </div>

          {/* Add custom provider form */}
          {showAddForm && (
            <div style={{
              marginBottom: 24, padding: '16px 18px',
              background: 'var(--card)', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
            }}>
              <p style={{
                margin: '0 0 14px', fontSize: 11, letterSpacing: '0.08em',
                textTransform: 'uppercase', color: 'var(--text-faint)',
                fontFamily: 'var(--font-mono)',
              }}>
                添加自定义服务商
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <input
                  className="input"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="服务商名称（如 Kimi、通义千问）"
                />
                <input
                  className="input"
                  value={newBaseUrl}
                  onChange={(e) => setNewBaseUrl(e.target.value)}
                  placeholder="API 地址（如 https://api.moonshot.cn/v1）"
                />
                <input
                  className="input"
                  type="password"
                  value={newApiKey}
                  onChange={(e) => setNewApiKey(e.target.value)}
                  placeholder="API Key（可选）"
                  autoComplete="off"
                />
                <input
                  className="input"
                  value={newModels}
                  onChange={(e) => setNewModels(e.target.value)}
                  placeholder="模型列表，逗号分隔（如 gpt-4o, gpt-4o-mini）"
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    className="btn"
                    onClick={addCustomProvider}
                    disabled={adding}
                    style={{ flex: 1 }}
                  >
                    {adding ? '添加中…' : '添加'}
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => setShowAddForm(false)}
                  >
                    取消
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* API Key */}
          {provider?.requires_key && (
            <div style={{ marginBottom: 24 }}>
              <label style={{
                display: 'block', marginBottom: 10, fontSize: 11,
                letterSpacing: '0.08em', textTransform: 'uppercase',
                color: 'var(--text-faint)', fontFamily: 'var(--font-mono)',
              }}>
                API Key
              </label>
              {keyAlreadyConfigured && !apiKey ? (
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '12px 14px', borderRadius: 'var(--radius-sm)',
                  background: 'var(--card)', border: '1px solid var(--hairline)',
                }}>
                  <span style={{ fontSize: 14, color: '#4ade80' }}>✓ 已配置</span>
                  <button
                    type="button"
                    onClick={() => setApiKey(' ')}
                    style={{
                      fontSize: 12, color: 'var(--text-dim)', background: 'none',
                      border: 'none', cursor: 'pointer', textDecoration: 'underline',
                    }}
                  >
                    更换
                  </button>
                </div>
              ) : (
                <input
                  className="input"
                  type="password"
                  value={apiKey}
                  onChange={(e) => { setApiKey(e.target.value); setSaved(false) }}
                  placeholder="sk-…"
                  autoComplete="off"
                />
              )}
            </div>
          )}

          {/* Model selection */}
          <div style={{ marginBottom: 24 }}>
            <label style={{
              display: 'block', marginBottom: 10, fontSize: 11,
              letterSpacing: '0.08em', textTransform: 'uppercase',
              color: 'var(--text-faint)', fontFamily: 'var(--font-mono)',
            }}>
              Model · 模型
            </label>

            {(provider?.models ?? []).length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                {(provider?.models ?? []).map((m) => (
                  <button
                    type="button"
                    key={m}
                    onClick={() => selectModel(m)}
                    style={{
                      padding: '6px 12px', borderRadius: 'var(--radius-xs)',
                      background: model === m && !customModel ? 'var(--accent)' : 'var(--card)',
                      border: `1px solid ${model === m && !customModel ? 'var(--accent)' : 'var(--hairline)'}`,
                      color: model === m && !customModel ? '#000' : 'var(--text-dim)',
                      fontSize: 13, fontFamily: 'var(--font-mono)',
                      cursor: 'pointer', transition: 'var(--transition)',
                    }}
                  >
                    {m}
                  </button>
                ))}
              </div>
            )}

            <input
              className="input"
              value={customModel}
              onChange={(e) => { setCustomModel(e.target.value); setModel(''); setSaved(false) }}
              placeholder={provider?.models?.length ? '或输入其他模型名称…' : '输入模型名称'}
              style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}
            />
          </div>

          {error && (
            <p className="error-text" role="alert" style={{ marginBottom: 12 }}>{error}</p>
          )}

          <button className="btn btn-block" disabled={saving}>
            {saving ? '保存中…' : '保存配置'}
          </button>
        </form>
      </div>
    </>
  )
}
