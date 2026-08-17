export function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((done / total) * 100)
  const segments = Math.max(total, 1)

  return (
    <div>
      <div className="progress-meta">
        <span className="progress-label">整体进度</span>
        <span className="progress-count">{done} / {total} · {pct}%</span>
      </div>
      <div className="progress-track" aria-label={`已完成 ${pct}%`}>
        {Array.from({ length: segments }, (_, i) => (
          <span key={i} className={`progress-seg ${i < done ? 'filled' : ''}`} />
        ))}
      </div>
    </div>
  )
}
