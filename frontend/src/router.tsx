import { createBrowserRouter } from 'react-router-dom'
import { GoalInput } from './pages/GoalInput'
import { PlanOverview } from './pages/PlanOverview'
import { DailyTasks } from './pages/DailyTasks'
import { LearningPage } from './pages/LearningPage'

export const router = createBrowserRouter([
  { path: '/', element: <GoalInput /> },
  { path: '/goals/:id', element: <PlanOverview /> },
  { path: '/goals/:id/daily', element: <DailyTasks /> },
  { path: '/tasks/:taskId/learn', element: <LearningPage /> },
])
