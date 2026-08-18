import type { ReactNode } from 'react'
import { createBrowserRouter } from 'react-router-dom'

import { useAuth } from './auth/AuthContext'
import { SetupGate } from './auth/SetupGate'
import { useI18n } from './i18n'
import { DailyTasks } from './pages/DailyTasks'
import { GoalInput } from './pages/GoalInput'
import { LearningPage } from './pages/LearningPage'
import { PlanOverview } from './pages/PlanOverview'
import { SetupPage } from './pages/SetupPage'


function RequireAuth({ children }: { children: ReactNode }) {
  const { loading } = useAuth()
  const { t } = useI18n()

  if (loading) {
    return <div className="page"><p className="faint">{t('loading')}</p></div>
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
