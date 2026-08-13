import { Link } from 'react-router-dom'
import type { GoalDTO } from '../types'
import { IconArrowRight, IconTrash } from './icons'

export function GoalList({ goals, onDelete }: { goals: GoalDTO[]; onDelete: (id: number) => void }) {
  if (goals.length === 0) return null
  return (
    <div style={{ marginTop: 28 }}>
      <h2 className="dim" style={{ fontSize: 15, marginBottom: 10 }}>历史目标</h2>
      {goals.map((g) => (
        <div
          key={g.id}
          className="card row-hover"
          style={{
            padding: '12px 14px', marginBottom: 10,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}
        >
          <Link to={`/goals/${g.id}`} style={{ fontWeight: 600, flex: 1 }}>
            {g.title}
          </Link>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              className="btn-ghost btn-icon btn-danger"
              onClick={() => onDelete(g.id)}
              aria-label="删除"
            >
              <IconTrash size={14} />
            </button>
            <Link to={`/goals/${g.id}`} className="dim" style={{ display: 'inline-flex' }} aria-label="打开">
              <IconArrowRight size={14} />
            </Link>
          </span>
        </div>
      ))}
    </div>
  )
}
