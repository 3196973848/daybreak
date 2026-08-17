export type TaskType = 'learn' | 'practice' | 'project'

export interface TaskDTO {
  id: number
  title: string
  description: string
  type: TaskType
  scheduled_date: string | null
  effort: number
  order: number
  status: 'todo' | 'done'
  verified: boolean
  completed_at: string | null
}

export interface MilestoneDTO {
  id: number
  title: string
  description: string
  order: number
  due_date: string | null
  status: 'todo' | 'active' | 'done'
  tasks: TaskDTO[]
}

export interface PlanDTO {
  id: number
  strategy: string
  status: string
  milestones: MilestoneDTO[]
}

export interface GoalDTO {
  id: number
  title: string
  description: string
  target_date: string | null
  created_at: string
  plan?: PlanDTO
}

export interface TestQuestionDTO {
  id: number
  type: 'choice' | 'short'
  text: string
  options: string[]
}

export interface TestContentDTO { questions: TestQuestionDTO[] }
export interface DeliverContentDTO { acceptance_criteria: string }

export interface VerificationStart {
  mode: 'test' | 'deliver'
  record_id: number
  content: TestContentDTO | DeliverContentDTO
}

export interface VerificationSubmit {
  record_id: number
  answers?: Record<number, string>
  submission?: string
}

export interface QuizQuestionResultDTO {
  id: number
  type: 'choice' | 'short'
  points: number
  correct?: boolean | null
  correct_answer?: string | null
  feedback: string
}

export interface VerificationResult {
  passed: boolean
  score: number
  feedback: string
  verified: boolean
  points?: number
  details?: QuizQuestionResultDTO[]
}

export type LearningStage = 'diagnose' | 'explain' | 'practice' | 'remediate' | 'ready'

export interface LearningTurnDTO {
  id: number
  client_turn_id: string
  user_message: string | null
  assistant_message: string
  stage: LearningStage
  created_at: string
}

export interface LearningSessionDTO {
  id: number
  task_id: number
  goal_id: number
  task_title: string
  task_description: string
  stage: LearningStage
  covered_points: string[]
  weak_points: string[]
  ready_for_verification: boolean
  estimated_hours_snapshot: number
  turns: LearningTurnDTO[]
}
