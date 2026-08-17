import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import type { GoalDTO } from '../types'
import { PlanOverview } from './PlanOverview'


vi.mock('../api/client', () => ({
  api: {
    getGoal: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

const goal: GoalDTO = {
  id: 1,
  title: '测试目标',
  description: '',
  target_date: null,
  created_at: '2026-08-13T00:00:00',
  plan: {
    id: 1,
    strategy: '策略',
    status: 'active',
    milestones: [{
      id: 1,
      title: '阶段',
      description: '',
      order: 1,
      due_date: null,
      status: 'todo',
      tasks: [],
    }],
  },
}

afterEach(cleanup)

describe('PlanOverview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.getGoal.mockResolvedValue(goal)
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn(() => 'blob:test')
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn()
    }
    HTMLAnchorElement.prototype.click = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => new Blob(['ics']),
    }))
  })

  it('downloads the ics calendar when the export button is clicked', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/goals/1']}>
        <Routes><Route path="/goals/:id" element={<PlanOverview />} /></Routes>
      </MemoryRouter>,
    )

    await user.click(await screen.findByRole('button', { name: /导出日历/ }))

    expect(fetch).toHaveBeenCalledWith('/api/goals/1/calendar.ics')
  })
})
