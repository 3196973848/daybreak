import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { I18nProvider, useI18n } from './i18n'

function Probe() {
  const { lang, setLang, t } = useI18n()
  return (
    <div>
      <span data-testid="lang">{lang}</span>
      <span data-testid="text">{t('generate')}</span>
      <button type="button" onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}>toggle</button>
    </div>
  )
}

afterEach(() => {
  cleanup()
  localStorage.removeItem('planagent_lang')
})

describe('I18nProvider', () => {
  beforeEach(() => {
    localStorage.removeItem('planagent_lang')
  })

  it('defaults to Chinese and switches to English with persistence', () => {
    render(<I18nProvider><Probe /></I18nProvider>)

    expect(screen.getByTestId('lang').textContent).toBe('zh')
    expect(screen.getByTestId('text').textContent).toBe('生成计划')

    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))

    expect(screen.getByTestId('lang').textContent).toBe('en')
    expect(screen.getByTestId('text').textContent).toBe('Generate plan')
    expect(localStorage.getItem('planagent_lang')).toBe('en')
  })

  it('restores the saved English preference on mount', () => {
    localStorage.setItem('planagent_lang', 'en')
    render(<I18nProvider><Probe /></I18nProvider>)

    expect(screen.getByTestId('lang').textContent).toBe('en')
    expect(screen.getByTestId('text').textContent).toBe('Generate plan')
  })

  it('fills template parameters in the active language', () => {
    localStorage.setItem('planagent_lang', 'en')
    render(<I18nProvider><ParamProbe /></I18nProvider>)
    expect(screen.getByTestId('param').textContent).toBe('Q3 · 8 / 10 pts')
  })
})

function ParamProbe() {
  const { t } = useI18n()
  return <span data-testid="param">{t('questionNo', { n: 3 })} · {t('pointsPer', { n: 8 })}</span>
}
