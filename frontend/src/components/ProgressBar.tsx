import { useI18n } from '../i18n'

export function ProgressBar({ done, total }: { done: number; total: number }) {
  const { t } = useI18n()
  const pct = total === 0 ? 0 : Math.round((done / total) * 100)
  const segments = Math.max(total, 1)

  return (
    <div>
      <div className="progress-meta">
        <span className="progress-label">{t('progressLabel')}</span>
        <span className="progress-count">{t('progressCount', { done, total, pct })}</span>
      </div>
      <div className="progress-track" aria-label={t('progressAria', { pct })}>
        {Array.from({ length: segments }, (_, i) => (
          <span key={i} className={`progress-seg ${i < done ? 'filled' : ''}`} />
        ))}
      </div>
    </div>
  )
}
