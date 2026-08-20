import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useI18n } from '../i18n'
import { IconArrowLeft, IconTarget } from './icons'

function IconSettings({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
    </svg>
  )
}

export function TopBar({
  title, backTo, actions,
}: { title?: string; backTo?: string; actions?: ReactNode }) {
  const { user, logout } = useAuth()
  const { lang, setLang, t } = useI18n()

  return (
    <nav className="topbar">
      <Link to="/" className="topbar-brand">
        <span className="brand-mark">
          <IconTarget size={16} />
        </span>
        <span>Daybreak</span>
      </Link>
      {title && <span className="topbar-title">{title}</span>}
      <div className="topbar-spacer" />
      {backTo && (
        <Link to={backTo} className="btn-ghost">
          <IconArrowLeft size={14} />
          {t('back')}
        </Link>
      )}
      <Link to="/setup" className="btn-ghost" title="API 设置">
        <IconSettings size={14} />
      </Link>
      <button
        type="button"
        className="btn-ghost lang-toggle"
        onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}
        aria-label={t('switchLang')}
      >
        {lang === 'zh' ? 'EN' : '中文'}
      </button>
      {user && user.auth_enabled !== false && (
        <button className="btn-ghost" onClick={() => void logout()}>
          {user.username} · {t('logout')}
        </button>
      )}
      {actions}
    </nav>
  )
}
