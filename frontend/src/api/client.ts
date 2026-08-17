import type {
  GoalDTO, LearningSessionDTO, TaskDTO, VerificationResult, VerificationStart,
  VerificationSubmit,
} from '../types'

const BASE = '/api'

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === 'string' ? detail : '请求失败')
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  let payload: unknown
  try {
    payload = await res.json()
  } catch (error) {
    if (!res.ok) throw new ApiError(res.status, res.statusText)
    throw error
  }
  if (!res.ok) {
    const detail = typeof payload === 'object'
      && payload !== null
      && 'detail' in payload
      ? payload.detail ?? res.statusText
      : res.statusText
    throw new ApiError(res.status, detail)
  }
  return payload as T
}

export type DurationUnit = 'day' | 'week' | 'month'

export interface CreateGoalInput {
  title: string
  description?: string
  duration_value: number
  duration_unit: DurationUnit
  daily_hours: number
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
  getLearningSession: (taskId: number) =>
    req<LearningSessionDTO>(`/tasks/${taskId}/learning-session`),
  startLearningSession: (taskId: number) =>
    req<LearningSessionDTO>(`/tasks/${taskId}/learning-session`, { method: 'POST' }),
  sendLearningTurn: (taskId: number, body: { client_turn_id: string; message: string }) =>
    req<LearningSessionDTO>(`/tasks/${taskId}/learning-session/turns`, {
      method: 'POST', body: JSON.stringify(body),
    }),
}
