import { Link } from 'react-router-dom'
import type { GoalDTO } from '../types'
import { IconArrowRight, IconTrash } from './icons'

export function GoalList({ goals, onDelete }: { goals: GoalDTO[]; onDelete: (id: number) => void }) {
  if (goals.length === 0) return null

  return (
    <div className="goal-list">
      <h2 className="section-title">历史目标</h2>
      {goals.map((g) => (
        <div key={g.id} className="card row-hover goal-row">
          <Link to={`/goals/${g.id}`} className="goal-row-main">
            <div className="goal-title">{g.title}</div>
            <div className="goal-meta">
              {g.target_date ? `截止 ${g.target_date}` : `创建于 ${g.created_at.slice(0, 10)}`}
            </div>
          </Link>
          <div className="goal-actions">
            <button
              className="btn-ghost btn-icon btn-danger"
              onClick={() => onDelete(g.id)}
              aria-label="删除"
            >
              <IconTrash size={14} />
            </button>
            <Link to={`/goals/${g.id}`} className="btn-ghost btn-icon" aria-label="打开">
              <IconArrowRight size={14} />
            </Link>
          </div>
        </div>
      ))}
    </div>
  )
}
