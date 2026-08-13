import { createBrowserRouter } from 'react-router-dom'
import { GoalInput } from './pages/GoalInput'
import { PlanOverview } from './pages/PlanOverview'
import { DailyTasks } from './pages/DailyTasks'

export const router = createBrowserRouter([
  { path: '/', element: <GoalInput /> },
  { path: '/goals/:id', element: <PlanOverview /> },
  { path: '/goals/:id/daily', element: <DailyTasks /> },
])
