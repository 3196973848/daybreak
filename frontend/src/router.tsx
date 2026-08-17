import type { ReactNode } from 'react'
import { createBrowserRouter } from 'react-router-dom'

import { useAuth } from './auth/AuthContext'
import { DailyTasks } from './pages/DailyTasks'
import { GoalInput } from './pages/GoalInput'
import { LearningPage } from './pages/LearningPage'
import { PlanOverview } from './pages/PlanOverview'


function RequireAuth({ children }: { children: ReactNode }) {
  const { loading } = useAuth()

  if (loading) {
    return <div className="page"><p className="faint">加载中…</p></div>
  }
  return <>{children}</>
}


export const router = createBrowserRouter([
  { path: '/', element: <RequireAuth><GoalInput /></RequireAuth> },
  { path: '/goals/:id', element: <RequireAuth><PlanOverview /></RequireAuth> },
  { path: '/goals/:id/daily', element: <RequireAuth><DailyTasks /></RequireAuth> },
  { path: '/tasks/:taskId/learn', element: <RequireAuth><LearningPage /></RequireAuth> },
])
