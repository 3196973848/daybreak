const WEEK = ['日', '一', '二', '三', '四', '五', '六']

export function Calendar({
  year, month, selected, datesWithTasks, onSelect,
}: {
  year: number
  month: number // 0-11
  selected: string
  datesWithTasks: Set<string>
  onSelect: (iso: string) => void
}) {
  const first = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const todayIso = new Date().toISOString().slice(0, 10)
  const cells: Array<number | null> = [...Array(first).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)]

  function onMonthChange(delta: number) {
    const d = new Date(year, month + delta, 1)
    onSelect(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`)
  }

  return (
    <div className="card" style={{ padding: 16, width: 250 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <button className="btn-ghost" onClick={() => onMonthChange(-1)}>‹</button>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{year}年{month + 1}月</span>
        <button className="btn-ghost" onClick={() => onMonthChange(1)}>›</button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 2, marginBottom: 4 }}>
        {WEEK.map((w) => <span key={w} style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-faint)' }}>{w}</span>)}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 2 }}>
        {cells.map((day, i) => {
          if (day === null) return <div key={`b${i}`} />
          const iso = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const isSel = iso === selected
          const isToday = iso === todayIso
          const hasTasks = datesWithTasks.has(iso)
          return (
            <div
              key={iso}
              onClick={() => onSelect(iso)}
              style={{
                width: 28, height: 28, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', fontSize: 12, borderRadius: 6, cursor: 'pointer',
                background: isSel ? 'var(--accent)' : undefined,
                color: isSel ? '#000' : hasTasks ? 'var(--text)' : 'var(--text-faint)',
                border: isToday ? '1px solid var(--text-faint)' : undefined,
              }}
            >
              {day}
              {hasTasks && !isSel && <span style={{ width: 4, height: 4, background: 'var(--accent)', borderRadius: 2 }} />}
            </div>
          )
        })}
      </div>
      <p className="faint" style={{ fontSize: 11, marginTop: 10 }}>• = 当天有任务</p>
    </div>
  )
}
