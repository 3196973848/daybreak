export function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((done / total) * 100)
  return (
    <div>
      <div className="dim" style={{ fontSize: 12, marginBottom: 6 }}>
        整体进度 · 已完成 {done} / {total} 个任务
      </div>
      <div style={{ background: 'var(--border)', borderRadius: 4, height: 8 }}>
        <div style={{ background: 'var(--accent)', borderRadius: 4, height: 8, width: `${pct}%` }} />
      </div>
    </div>
  )
}
