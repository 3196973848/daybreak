import type {
  GoalDTO, TaskDTO, VerificationResult, VerificationStart, VerificationSubmit,
} from '../types'

const BASE = '/api'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* keep default */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export type DurationUnit = 'day' | 'week' | 'month'

export interface CreateGoalInput {
  title: string
  description?: string
  duration_value: number
  duration_unit: DurationUnit
}

export const api = {
  createGoal: (body: CreateGoalInput) =>
    req<GoalDTO>('/goals', { method: 'POST', body: JSON.stringify(body) }),
  listGoals: () => req<GoalDTO[]>('/goals'),
  getGoal: (id: number) => req<GoalDTO>(`/goals/${id}`),
  deleteGoal: (id: number) => req<{ ok: boolean }>(`/goals/${id}`, { method: 'DELETE' }),
  setTaskCompleted: (id: number, completed: boolean) =>
    req<TaskDTO>(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify({ completed }) }),
  getVerification: (taskId: number) =>
    req<VerificationStart>(`/tasks/${taskId}/verification`),
  submitVerification: (taskId: number, body: VerificationSubmit) =>
    req<VerificationResult>(`/tasks/${taskId}/verification`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
