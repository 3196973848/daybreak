import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useI18n } from '../i18n'
import { IconArrowLeft, IconTarget } from './icons'

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
        <span>PlanAgent</span>
      </Link>
      {title && <span className="topbar-title">{title}</span>}
      <div className="topbar-spacer" />
      {backTo && (
        <Link to={backTo} className="btn-ghost">
          <IconArrowLeft size={14} />
          {t('back')}
        </Link>
      )}
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
