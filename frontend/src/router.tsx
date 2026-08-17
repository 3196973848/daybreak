import type { ReactNode } from 'react'
import { createBrowserRouter } from 'react-router-dom'

import { useAuth } from './auth/AuthContext'
import { SetupGate } from './auth/SetupGate'
import { DailyTasks } from './pages/DailyTasks'
import { GoalInput } from './pages/GoalInput'
import { LearningPage } from './pages/LearningPage'
import { PlanOverview } from './pages/PlanOverview'
import { SetupPage } from './pages/SetupPage'


function RequireAuth({ children }: { children: ReactNode }) {
  const { loading } = useAuth()

  if (loading) {
    return <div className="page"><p className="faint">加载中…</p></div>
  }
  return <>{children}</>
}


export const router = createBrowserRouter([
  { path: '/setup', element: <SetupGate><SetupPage /></SetupGate> },
  {
    path: '/',
    element: (
      <SetupGate><RequireAuth><GoalInput /></RequireAuth></SetupGate>
    ),
  },
  {
    path: '/goals/:id',
    element: (
      <SetupGate><RequireAuth><PlanOverview /></RequireAuth></SetupGate>
    ),
  },
  {
    path: '/goals/:id/daily',
    element: (
      <SetupGate><RequireAuth><DailyTasks /></RequireAuth></SetupGate>
    ),
  },
  {
    path: '/tasks/:taskId/learn',
    element: (
      <SetupGate><RequireAuth><LearningPage /></RequireAuth></SetupGate>
    ),
  },
])
