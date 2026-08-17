import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { IconArrowLeft, IconTarget } from './icons'

export function TopBar({
  title, backTo, actions,
}: { title?: string; backTo?: string; actions?: ReactNode }) {
  const { user, logout } = useAuth()

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
          返回
        </Link>
      )}
      {user && (
        <button className="btn-ghost" onClick={() => void logout()}>
          {user.username} · 退出
        </button>
      )}
      {actions}
    </nav>
  )
}
