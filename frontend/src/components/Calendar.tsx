import { todayLocal } from '../utils/date'
import { useI18n } from '../i18n'

const WEEK_KEYS = ['weekSun', 'weekMon', 'weekTue', 'weekWed', 'weekThu', 'weekFri', 'weekSat']

export function Calendar({
  year, month, selected, datesWithTasks, onSelect,
}: {
  year: number
  month: number // 0-11
  selected: string
  datesWithTasks: Set<string>
  onSelect: (iso: string) => void
}) {
  const { t } = useI18n()
  const first = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const todayIso = todayLocal()
  const cells: Array<number | null> = [
    ...Array(first).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  function onMonthChange(delta: number) {
    const d = new Date(year, month + delta, 1)
    onSelect(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`)
  }

  return (
    <div className="card calendar">
      <div className="calendar-head">
        <button type="button" className="btn-ghost btn-icon" onClick={() => onMonthChange(-1)} aria-label={t('prevMonth')}>
          ‹
        </button>
        <span className="calendar-month">{t('calendarMonth', { year, month: month + 1 })}</span>
        <button type="button" className="btn-ghost btn-icon" onClick={() => onMonthChange(1)} aria-label={t('nextMonth')}>
          ›
        </button>
      </div>

      <div className="calendar-grid">
        {WEEK_KEYS.map((key) => (
          <span key={key} className="calendar-weekday">{t(key)}</span>
        ))}
        {cells.map((day, i) => {
          if (day === null) return <span key={`blank-${i}`} />

          const iso = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const isSelected = iso === selected
          const isToday = iso === todayIso
          const hasTasks = datesWithTasks.has(iso)
          const className = [
            'calendar-cell',
            isSelected ? 'selected' : '',
            isToday ? 'today' : '',
            hasTasks ? 'has-tasks' : '',
          ].filter(Boolean).join(' ')

          return (
            <button type="button" key={iso} className={className} onClick={() => onSelect(iso)}>
              {day}
              {hasTasks && !isSelected && <span className="calendar-dot" />}
            </button>
          )
        })}
      </div>

      <p className="calendar-legend">{t('calendarLegend')}</p>
    </div>
  )
}
