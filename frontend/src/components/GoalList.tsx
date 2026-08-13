import { Link } from 'react-router-dom'
import type { GoalDTO } from '../types'

export function GoalList({ goals, onDelete }: { goals: GoalDTO[]; onDelete: (id: number) => void }) {
  if (goals.length === 0) return null
  return (
    <div style={{ marginTop: 24 }}>
      <h2 className="dim" style={{ fontSize: 15 }}>历史目标</h2>
      {goals.map((g) => (
        <div key={g.id} className="card" style={{ padding: 14, marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Link to={`/goals/${g.id}`} style={{ fontWeight: 600 }}>{g.title}</Link>
          <button className="btn-ghost" onClick={() => onDelete(g.id)}>删除</button>
        </div>
      ))}
    </div>
  )
}
