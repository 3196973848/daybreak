import type {
  GoalDTO, LearningSessionDTO, ModelsDTO, TaskDTO, UserDTO,
  SettingsDTO, SettingsUpdate, VerificationResult, VerificationStart,
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
  getModels: () => req<ModelsDTO>('/settings/models'),
  getSettings: () => req<SettingsDTO>('/settings'),
  saveSettings: (body: SettingsUpdate) =>
    req<SettingsDTO>('/settings', { method: 'POST', body: JSON.stringify(body) }),
  register: (username: string, password: string) =>
    req<UserDTO>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  login: (username: string, password: string) =>
    req<UserDTO>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () =>
    req<{ ok: boolean }>('/auth/logout', { method: 'POST' }),
  me: () => req<UserDTO>('/auth/me'),
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
  streamTutorTurn: async (
    taskId: number,
    body: { client_turn_id: string; message: string; model?: string },
    handlers: {
      onReply: (text: string) => void
      onDone: (session: LearningSessionDTO) => void
      onError: (message: string) => void
    },
  ) => {
    const res = await fetch(`${BASE}/tasks/${taskId}/learning-session/turns/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok || !res.body) {
      let detail: unknown = res.statusText
      try { detail = (await res.json()).detail ?? detail } catch { /* keep default */ }
      handlers.onError(typeof detail === 'string' ? detail : '发送失败')
      return
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let separator: number
      while ((separator = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, separator)
        buffer = buffer.slice(separator + 2)
        const lines = raw.split('\n')
        const event = lines.find((line) => line.startsWith('event: '))?.slice(7) ?? 'error'
        const dataLine = lines.find((line) => line.startsWith('data: '))?.slice(6)
        if (!dataLine) continue
        let payload: unknown
        try { payload = JSON.parse(dataLine) } catch { continue }
        if (event === 'reply' && payload && typeof payload === 'object' && 'text' in payload) {
          handlers.onReply(String((payload as { text: string }).text))
        } else if (event === 'done' && payload) {
          handlers.onDone(payload as LearningSessionDTO)
        } else if (event === 'error' && payload && typeof payload === 'object' && 'message' in payload) {
          handlers.onError(String((payload as { message: string }).message))
        }
      }
    }
  },
}
