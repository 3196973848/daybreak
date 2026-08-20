import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '../api/client'
import { GoalInput } from './GoalInput'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    api: {
      ...actual.api,
      listGoals: vi.fn(),
      createGoal: vi.fn(),
      deleteGoal: vi.fn(),
    },
  }
})

const mockedApi = vi.mocked(api)

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('preserves API status when an error response is not JSON', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false,
    status: 503,
    statusText: 'Service Unavailable',
    json: vi.fn().mockRejectedValue(new SyntaxError('Unexpected end of JSON input')),
  }))

  await expect(api.getGoal(1)).rejects.toMatchObject({
    status: 503,
    detail: 'Service Unavailable',
    message: 'Service Unavailable',
  })
})

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
    const dailyHours = screen.getByLabelText('每日可投入时间') as HTMLInputElement
    expect(duration.value).toBe('30')
    expect(unit.value).toBe('day')
    expect(dailyHours.value).toBe('2')
    expect(dailyHours.step).toBe('0.5')

    await user.type(screen.getByLabelText('目标标题 *'), '学习 Python')
    fireEvent.change(duration, { target: { value: '3' } })
    fireEvent.change(dailyHours, { target: { value: '2.5' } })
    await user.selectOptions(unit, 'month')
    await user.click(screen.getByRole('button', { name: '生成计划' }))

    await waitFor(() => {
      expect(mockedApi.createGoal).toHaveBeenCalledWith({
        title: '学习 Python',
        description: '',
        duration_value: 3,
        duration_unit: 'month',
        daily_hours: 2.5,
      })
    })
  })

  it.each([
    ['an empty value', ''],
    ['zero', 0],
    ['a negative value', -0.5],
    ['a non-half-hour increment', 0.75],
  ])('rejects daily hours that are %s', async (_case, enteredValue) => {
    const user = userEvent.setup()
    render(<MemoryRouter><GoalInput /></MemoryRouter>)

    await user.type(screen.getByLabelText('目标标题 *'), '学习 Python')
    fireEvent.change(screen.getByLabelText('每日可投入时间'), {
      target: { value: enteredValue },
    })
    await user.click(screen.getByRole('button', { name: '生成计划' }))

    expect((await screen.findByRole('alert')).textContent).toContain(
      '每日可投入时间必须是 0.5 小时的正数倍',
    )
    expect(mockedApi.createGoal).not.toHaveBeenCalled()
  })

  it('shows required capacity and suggested days from a structured API error', async () => {
    mockedApi.createGoal.mockRejectedValue(new ApiError(422, {
      code: 'insufficient_capacity', message: '当前时间不足',
      required_hours: 12, available_hours: 8, minimum_days: 6,
      suggested_duration: { value: 6, unit: 'day' },
    }))
    const user = userEvent.setup()
    render(<MemoryRouter><GoalInput /></MemoryRouter>)

    await user.type(screen.getByLabelText('目标标题 *'), '学习 Python')
    await user.click(screen.getByRole('button', { name: '生成计划' }))

    expect((await screen.findByRole('alert')).textContent).toContain(
      '当前时间不足：计划约需 12 小时，现有周期可用 8 小时。建议至少设置 6 天，或提高每日投入时间。',
    )
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
