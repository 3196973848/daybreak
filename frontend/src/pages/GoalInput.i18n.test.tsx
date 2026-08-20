import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import { I18nProvider } from '../i18n'
import { GoalInput } from './GoalInput'

vi.mock('../api/client', () => ({
  api: {
    listGoals: vi.fn(),
    createGoal: vi.fn(),
    deleteGoal: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

afterEach(() => {
  cleanup()
  localStorage.removeItem('planagent_lang')
})

describe('GoalInput language switching', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.removeItem('planagent_lang')
    mockedApi.listGoals.mockResolvedValue([])
  })

  it('toggles the whole page between Chinese and English from the top bar', async () => {
    const user = userEvent.setup()
    render(
      <I18nProvider>
        <MemoryRouter><GoalInput /></MemoryRouter>
      </I18nProvider>,
    )

    expect(screen.getByRole('heading', { name: '把模糊的愿景，变成每一天的行动' })).toBeTruthy()
    expect(screen.getByLabelText('目标标题 *')).toBeTruthy()

    await user.click(screen.getByRole('button', { name: 'English' }))

    expect(screen.getByRole('heading', { name: 'Turn vague visions into daily actions' })).toBeTruthy()
    expect(screen.getByLabelText('Goal title *')).toBeTruthy()
    expect(localStorage.getItem('planagent_lang')).toBe('en')

    await user.click(screen.getByRole('button', { name: '中文' }))

    expect(screen.getByRole('heading', { name: '把模糊的愿景，变成每一天的行动' })).toBeTruthy()
  })
})
