import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { api } from '../api/client'
import type { SettingsDTO } from '../types'


let cachedSettings: SettingsDTO | null = null
let settingsPromise: Promise<SettingsDTO> | null = null

function loadSettings(): Promise<SettingsDTO> {
  if (cachedSettings) return Promise.resolve(cachedSettings)
  if (!settingsPromise) {
    settingsPromise = api.getSettings()
      .then((value) => {
        cachedSettings = value
        return value
      })
      .catch(() => ({
        configured: true,
        provider: 'deepseek',
        providers: [],
        model: '',
        models: [],
        requires_key: true,
      }))
  }
  return settingsPromise
}


export function SetupGate({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<SettingsDTO | null>(null)
  const location = useLocation()

  useEffect(() => {
    let active = true
    void loadSettings().then((value) => {
      if (active) setSettings(value)
    })
    return () => {
      active = false
    }
  }, [])

  if (!settings) {
    return <div className="page"><p className="faint">加载中…</p></div>
  }
  if (!settings.configured && location.pathname !== '/setup') {
    return <Navigate to="/setup" replace />
  }
  if (settings.configured && location.pathname === '/setup') {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}
