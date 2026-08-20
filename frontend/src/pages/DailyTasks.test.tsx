import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import type { GoalDTO, TaskDTO } from '../types'
import { DailyTasks } from './DailyTasks'
import '../index.css'

vi.mock('../api/client', () => ({
  api: {
    getGoal: vi.fn(),
    setTaskCompleted: vi.fn(),
    getLearningSession: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)
const task: TaskDTO = {
  id: 7,
  title: '完成练习',
  description: '',
  type: 'practice',
  scheduled_date: new Date().toLocaleDateString('en-CA'),
  effort: 1,
  actual_minutes: null,
  order: 0,
  status: 'todo',
  verified: false,
  completed_at: null,
}
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
      tasks: [task],
    }],
  },
}

afterEach(cleanup)

describe('DailyTasks completion control', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.getGoal.mockResolvedValue(goal)
    mockedApi.getLearningSession.mockResolvedValue({
      id: 41,
      task_id: 7,
      goal_id: 1,
      task_title: '理解闭包',
      task_description: '',
      stage: 'diagnose',
      covered_points: [],
      weak_points: [],
      ready_for_verification: false,
      estimated_hours_snapshot: 1,
      turns: [],
    })
    mockedApi.setTaskCompleted.mockResolvedValue({
      ...task,
      status: 'done',
      completed_at: '2026-08-13T12:00:00',
    })
  })

  it('turns the outlined circle into a filled check control after completion', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/goals/1/daily']}>
        <Routes><Route path="/goals/:id/daily" element={<DailyTasks />} /></Routes>
      </MemoryRouter>,
    )

    const toggle = await screen.findByRole('button', { name: '标记完成' })
    expect(toggle.classList.contains('done')).toBe(false)
    expect(toggle.querySelector('svg')).toBeNull()
    const outlinedStyle = getComputedStyle(toggle)
    expect(outlinedStyle.width).toBe('20px')
    expect(outlinedStyle.height).toBe('20px')
    expect(outlinedStyle.borderRadius).toBe('50%')
    expect(outlinedStyle.borderTopStyle).toBe('solid')
    expect(outlinedStyle.borderTopWidth).toBe('2px')
    expect(['transparent', 'rgba(0, 0, 0, 0)']).not.toContain(outlinedStyle.borderTopColor)
    expect(['transparent', 'rgba(0, 0, 0, 0)']).toContain(outlinedStyle.backgroundColor)

    await user.click(toggle)

    await waitFor(() => {
      const completed = screen.getByRole('button', { name: '标记未完成' })
      expect(completed.classList.contains('done')).toBe(true)
      const check = completed.querySelector('svg')
      expect(check).not.toBeNull()
      expect(check?.getAttribute('width')).toBe('13')
      expect(check?.getAttribute('height')).toBe('13')
      expect(check?.getAttribute('stroke')).toBe('currentColor')
      const style = getComputedStyle(completed)
      expect(style.width).toBe('20px')
      expect(style.height).toBe('20px')
      expect(style.borderRadius).toBe('50%')
      expect(style.borderTopColor).toBe('rgb(245, 245, 245)')
      expect(style.backgroundColor).toBe('rgb(245, 245, 245)')
      expect(style.color).toBe('rgb(23, 23, 23)')
    })
    expect(mockedApi.setTaskCompleted).toHaveBeenCalledWith(7, true)
  })

  it('shows a start-learning link for a learn task without a session', async () => {
    const learnTask: TaskDTO = { ...task, id: 7, type: 'learn', title: '理解闭包' }
    mockedApi.getGoal.mockResolvedValue({
      ...goal,
      plan: {
        ...goal.plan!,
        milestones: [{ ...goal.plan!.milestones[0], tasks: [learnTask] }],
      },
    })
    mockedApi.getLearningSession.mockRejectedValue(new Error('not found'))

    render(
      <MemoryRouter initialEntries={['/goals/1/daily']}>
        <Routes><Route path="/goals/:id/daily" element={<DailyTasks />} /></Routes>
      </MemoryRouter>,
    )

    const link = await screen.findByRole('link', { name: '开始学习' })
    expect(link.getAttribute('href')).toBe('/tasks/7/learn')
  })

  it('labels an existing learning session as continue', async () => {
    const learnTask: TaskDTO = { ...task, id: 7, type: 'learn', title: '理解闭包' }
    mockedApi.getGoal.mockResolvedValue({
      ...goal,
      plan: {
        ...goal.plan!,
        milestones: [{ ...goal.plan!.milestones[0], tasks: [learnTask] }],
      },
    })

    render(
      <MemoryRouter initialEntries={['/goals/1/daily']}>
        <Routes><Route path="/goals/:id/daily" element={<DailyTasks />} /></Routes>
      </MemoryRouter>,
    )

    const link = await screen.findByRole('link', { name: '继续学习' })
    expect(link.getAttribute('href')).toBe('/tasks/7/learn')
  })

  it('renders no learning link for practice tasks', async () => {
    render(
      <MemoryRouter initialEntries={['/goals/1/daily']}>
        <Routes><Route path="/goals/:id/daily" element={<DailyTasks />} /></Routes>
      </MemoryRouter>,
    )

    await screen.findByRole('button', { name: '标记完成' })
    expect(screen.queryByRole('link', { name: /学习/ })).toBeNull()
  })
})
