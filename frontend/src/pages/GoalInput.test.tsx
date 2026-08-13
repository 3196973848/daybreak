import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import { GoalInput } from './GoalInput'

vi.mock('../api/client', () => ({
  api: {
    listGoals: vi.fn(),
    createGoal: vi.fn(),
    deleteGoal: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

afterEach(cleanup)

describe('GoalInput duration scheduling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.listGoals.mockResolvedValue([])
    mockedApi.createGoal.mockResolvedValue({
      id: 1,
      title: '学习 Python',
      description: '',
      target_date: '2026-11-13',
      created_at: '2026-08-13T00:00:00',
    })
  })

  it('submits a positive duration value and selected unit instead of a date', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><GoalInput /></MemoryRouter>)

    expect(screen.queryByLabelText('目标完成日期(可选)')).toBeNull()
    const duration = screen.getByLabelText('预期完成时间') as HTMLInputElement
    const unit = screen.getByLabelText('时间单位') as HTMLSelectElement
    expect(duration.value).toBe('30')
    expect(unit.value).toBe('day')

    await user.type(screen.getByLabelText('目标标题 *'), '学习 Python')
    fireEvent.change(duration, { target: { value: '3' } })
    await user.selectOptions(unit, 'month')
    await user.click(screen.getByRole('button', { name: '生成计划' }))

    await waitFor(() => {
      expect(mockedApi.createGoal).toHaveBeenCalledWith({
        title: '学习 Python',
        description: '',
        duration_value: 3,
        duration_unit: 'month',
      })
    })
  })

  it.each([
    ['an empty value', '', ''],
    ['zero', '0', '0'],
    ['a negative value', '-1', '-1'],
    ['a fractional value', '1.5', '1.5'],
    ['invalid text cleaned by the number input', 'invalid', ''],
  ])('rejects %s and exposes an accessible error', async (_case, enteredValue, browserValue) => {
    const user = userEvent.setup()
    render(<MemoryRouter><GoalInput /></MemoryRouter>)

    await user.type(screen.getByLabelText('目标标题 *'), '学习 Python')
    const duration = screen.getByLabelText('预期完成时间') as HTMLInputElement
    fireEvent.change(duration, { target: { value: enteredValue } })
    expect(duration.value).toBe(browserValue)
    await user.click(screen.getByRole('button', { name: '生成计划' }))

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toBe('预期完成时间必须是正整数')
    expect(alert.id).toBe('duration-error')
    expect(duration.getAttribute('aria-invalid')).toBe('true')
    expect(duration.getAttribute('aria-describedby')).toBe('duration-error')
    expect(mockedApi.createGoal).not.toHaveBeenCalled()
  })
})
