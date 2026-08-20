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
  target_date?: string
  duration_value?: number
  duration_unit?: DurationUnit
  daily_hours: number
  rejected_assumptions?: string[]
  rest_days?: number[]
}

export const api = {
  getModels: () => req<ModelsDTO>('/settings/models'),
  getSettings: () => req<SettingsDTO>('/settings'),
  saveSettings: (body: SettingsUpdate) =>
    req<SettingsDTO>('/settings', { method: 'POST', body: JSON.stringify(body) }),
  createCustomProvider: (body: { name: string; base_url: string; api_key?: string; models?: string[] }) =>
    req<SettingsDTO>('/settings/providers', { method: 'POST', body: JSON.stringify(body) }),
  deleteCustomProvider: (id: string) =>
    req<SettingsDTO>(`/settings/providers/${id}`, { method: 'DELETE' }),
  addLeave: (goalId: number, leaveDate: string) =>
    req<GoalDTO>(`/goals/${goalId}/leave`, { method: 'POST', body: JSON.stringify({ date: leaveDate }) }),
  removeLeave: (goalId: number, leaveDate: string) =>
    req<GoalDTO>(`/goals/${goalId}/leave/${leaveDate}`, { method: 'DELETE' }),
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
  previewGoal: (body: CreateGoalInput) =>
    req<{ strategy: string; assumptions: string[]; milestones: any[]; total_hours: number; min_days: number; suggestion: { type: string; message: string; recommended_days?: number; recommended_date?: string; current_days?: number } | null }>('/goals/preview', {
      method: 'POST', body: JSON.stringify(body),
    }),
  replanGoal: (id: number, dailyHours?: number, restDays?: number[]) =>
    req<GoalDTO>(`/goals/${id}/replan`, { method: 'POST', body: JSON.stringify({ daily_hours: dailyHours, rest_days: restDays }) }),
  replanPreview: (id: number, dailyHours?: number, restDays?: number[]) =>
    req<{ changes: { task_id: number; title: string; old_date: string | null; new_date: string | null }[]; total_days: number; daily_hours: number }>(
      `/goals/${id}/replan/preview?${dailyHours ? `daily_hours=${dailyHours}&` : ''}${restDays?.length ? `rest_days=${restDays.join(',')}` : ''}`
    ),
  getPace: (id: number) =>
    req<{
      total_tasks: number; completed_tasks: number;
      planned_hours: number; actual_hours: number; deviation_pct: number;
      estimated_completion_date: string | null;
      suggestion: { type: string; message: string } | null;
    }>(`/goals/${id}/pace`),
  getReview: (id: number, week?: string) =>
    req<{
      year: number; week: number; start_date: string; end_date: string;
      completion_rate: number;
      total_planned: number; total_completed: number;
      total_actual_minutes: number;
      verification_count: number; verified_count: number; verification_rate: number;
      daily: { date: string; weekday: string; planned_tasks: number; completed_tasks: number; actual_minutes: number }[];
      conclusion: string;
    }>(`/goals/${id}/review${week ? `?week=${week}` : ''}`),
}
