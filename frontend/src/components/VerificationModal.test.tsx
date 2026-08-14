import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import type {
  TaskDTO, VerificationResult, VerificationStart,
} from '../types'
import { VerificationModal } from './VerificationModal'

vi.mock('../api/client', () => ({
  api: {
    getVerification: vi.fn(),
    submitVerification: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const task: TaskDTO = {
  id: 7,
  title: '练习数组方法',
  description: '掌握 map、filter 和 reduce',
  type: 'learn',
  scheduled_date: '2026-08-14',
  effort: 1,
  order: 0,
  status: 'todo',
  verified: false,
  completed_at: null,
}

const quizStart: VerificationStart = {
  mode: 'test',
  record_id: 42,
  content: {
    questions: [
      { id: 1, type: 'choice', text: '选择题 1', options: ['A', 'B', 'C', 'D'] },
      { id: 2, type: 'choice', text: '选择题 2', options: ['A', 'B', 'C', 'D'] },
      { id: 3, type: 'choice', text: '选择题 3', options: ['A', 'B', 'C', 'D'] },
      { id: 4, type: 'choice', text: '选择题 4', options: ['A', 'B', 'C', 'D'] },
      { id: 5, type: 'choice', text: '选择题 5', options: ['A', 'B', 'C', 'D'] },
      { id: 6, type: 'choice', text: '选择题 6', options: ['A', 'B', 'C', 'D'] },
      { id: 7, type: 'choice', text: '选择题 7', options: ['A', 'B', 'C', 'D'] },
      { id: 8, type: 'short', text: '简答题 8', options: [] },
      { id: 9, type: 'short', text: '简答题 9', options: [] },
      { id: 10, type: 'short', text: '简答题 10', options: [] },
    ],
  },
}

const detailedResult: VerificationResult = {
  passed: true,
  score: 0.7,
  points: 70,
  feedback: '达到通过标准',
  verified: true,
  details: [
    { id: 1, type: 'choice', points: 10, correct: true, correct_answer: 'A', feedback: '' },
    { id: 2, type: 'choice', points: 10, correct: true, correct_answer: 'B', feedback: '' },
    { id: 3, type: 'choice', points: 10, correct: true, correct_answer: 'A', feedback: '' },
    { id: 4, type: 'choice', points: 10, correct: true, correct_answer: 'A', feedback: '' },
    { id: 5, type: 'choice', points: 10, correct: true, correct_answer: 'A', feedback: '' },
    { id: 6, type: 'choice', points: 10, correct: true, correct_answer: 'A', feedback: '' },
    { id: 7, type: 'choice', points: 0, correct: false, correct_answer: 'C', feedback: '' },
    { id: 8, type: 'short', points: 5, feedback: '需要补充边界条件' },
    { id: 9, type: 'short', points: 5, feedback: '解释清楚' },
    { id: 10, type: 'short', points: 0, feedback: '示例可以更具体' },
  ],
}

afterEach(cleanup)

describe('VerificationModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows an indeterminate progress bar and no submit button while generating', () => {
    const generation = deferred<VerificationStart>()
    mockedApi.getVerification.mockReturnValue(generation.promise)

    render(<VerificationModal task={task} onClose={vi.fn()} />)

    const progress = screen.getByRole('progressbar', { name: '正在生成 10 道题' })
    expect(progress.getAttribute('aria-valuetext')).toBe('生成中')
    expect(progress.hasAttribute('aria-valuenow')).toBe(false)
    expect(screen.getByText('正在生成 10 道题…')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '提交检验' })).toBeNull()
  })

  it('renders all seven public choice questions and three public short questions after generation', async () => {
    mockedApi.getVerification.mockResolvedValue(quizStart)

    render(<VerificationModal task={task} onClose={vi.fn()} />)

    for (let id = 1; id <= 7; id += 1) {
      expect(await screen.findByText(`选择题 ${id}`)).toBeTruthy()
    }
    for (let id = 8; id <= 10; id += 1) {
      expect(await screen.findByText(`简答题 ${id}`)).toBeTruthy()
    }
    expect(screen.getByRole('button', { name: '提交检验' })).toBeTruthy()
    expect(screen.queryByText(/正确答案/)).toBeNull()
  })

  it('shows a generation error and retries generation for the current task', async () => {
    const user = userEvent.setup()
    const retry = deferred<VerificationStart>()
    mockedApi.getVerification
      .mockRejectedValueOnce(new Error('题目生成失败'))
      .mockReturnValueOnce(retry.promise)

    render(<VerificationModal task={task} onClose={vi.fn()} />)

    expect((await screen.findByRole('alert')).textContent).toBe('题目生成失败')
    await user.click(screen.getByRole('button', { name: '重新生成' }))

    await waitFor(() => expect(mockedApi.getVerification).toHaveBeenCalledTimes(2))
    expect(mockedApi.getVerification).toHaveBeenNthCalledWith(1, task.id)
    expect(mockedApi.getVerification).toHaveBeenNthCalledWith(2, task.id)
    expect(screen.getByRole('progressbar', { name: '正在生成 10 道题' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '提交检验' })).toBeNull()
    expect(mockedApi.submitVerification).not.toHaveBeenCalled()
  })

  it('ignores a stale generation response after the current task changes', async () => {
    const firstGeneration = deferred<VerificationStart>()
    const currentGeneration = deferred<VerificationStart>()
    mockedApi.getVerification
      .mockReturnValueOnce(firstGeneration.promise)
      .mockReturnValueOnce(currentGeneration.promise)
    const { rerender } = render(<VerificationModal task={task} onClose={vi.fn()} />)

    rerender(<VerificationModal task={{ ...task, id: 8, title: '当前任务' }} onClose={vi.fn()} />)
    await act(async () => {
      firstGeneration.resolve(quizStart)
      await firstGeneration.promise
    })

    expect(screen.queryByText('选择题 1')).toBeNull()
    expect(screen.getByRole('progressbar', { name: '正在生成 10 道题' })).toBeTruthy()
  })

  it('clears a completed result when the current task changes', async () => {
    const user = userEvent.setup()
    const currentGeneration = deferred<VerificationStart>()
    mockedApi.getVerification
      .mockResolvedValueOnce(quizStart)
      .mockReturnValueOnce(currentGeneration.promise)
    mockedApi.submitVerification.mockResolvedValue(detailedResult)
    const { rerender } = render(<VerificationModal task={task} onClose={vi.fn()} />)
    await user.click(await screen.findByRole('button', { name: '提交检验' }))
    expect(await screen.findByText('总分：70 / 100')).toBeTruthy()

    rerender(<VerificationModal task={{ ...task, id: 8, title: '当前任务' }} onClose={vi.fn()} />)

    expect(screen.queryByText('总分：70 / 100')).toBeNull()
    expect(screen.getByRole('progressbar', { name: '正在生成 10 道题' })).toBeTruthy()
  })

  it('clears answers when the current task changes', async () => {
    const user = userEvent.setup()
    mockedApi.getVerification
      .mockResolvedValueOnce(quizStart)
      .mockResolvedValueOnce({ ...quizStart, record_id: 43 })
    const { rerender } = render(<VerificationModal task={task} onClose={vi.fn()} />)
    const firstAnswer = (await screen.findAllByRole('radio', { name: 'A' }))[0] as HTMLInputElement
    await user.click(firstAnswer)
    expect(firstAnswer.checked).toBe(true)

    rerender(<VerificationModal task={{ ...task, id: 8, title: '当前任务' }} onClose={vi.fn()} />)

    await waitFor(() => expect(mockedApi.getVerification).toHaveBeenCalledTimes(2))
    await waitFor(() => {
      const currentFirstAnswer = screen.getAllByRole('radio', { name: 'A' })[0] as HTMLInputElement
      expect(currentFirstAnswer.checked).toBe(false)
    })
  })

  it('ignores a stale submission result after the current task changes', async () => {
    const user = userEvent.setup()
    const oldSubmission = deferred<VerificationResult>()
    const currentGeneration = deferred<VerificationStart>()
    const onVerified = vi.fn()
    mockedApi.getVerification
      .mockResolvedValueOnce(quizStart)
      .mockReturnValueOnce(currentGeneration.promise)
    mockedApi.submitVerification.mockReturnValue(oldSubmission.promise)
    const { rerender } = render(
      <VerificationModal task={task} onClose={vi.fn()} onVerified={onVerified} />,
    )
    await user.click(await screen.findByRole('button', { name: '提交检验' }))

    rerender(
      <VerificationModal
        task={{ ...task, id: 8, title: '当前任务' }}
        onClose={vi.fn()}
        onVerified={onVerified}
      />,
    )
    await act(async () => {
      oldSubmission.resolve(detailedResult)
      await oldSubmission.promise
    })

    expect(screen.queryByText('总分：70 / 100')).toBeNull()
    expect(screen.getByRole('progressbar', { name: '正在生成 10 道题' })).toBeTruthy()
    expect(onVerified).not.toHaveBeenCalled()
  })

  it('keeps submission state separate from generation state', async () => {
    const user = userEvent.setup()
    const submission = deferred<VerificationResult>()
    mockedApi.getVerification.mockResolvedValue(quizStart)
    mockedApi.submitVerification.mockReturnValue(submission.promise)
    render(<VerificationModal task={task} onClose={vi.fn()} />)

    await user.click(await screen.findByRole('button', { name: '提交检验' }))

    const submittingButton = screen.getByRole('button', { name: 'AI 评审中…' }) as HTMLButtonElement
    expect(submittingButton.disabled).toBe(true)
    expect(screen.queryByRole('progressbar', { name: '正在生成 10 道题' })).toBeNull()
  })

  it('renders total points and transparent per-question results after a test submission', async () => {
    const user = userEvent.setup()
    mockedApi.getVerification.mockResolvedValue(quizStart)
    mockedApi.submitVerification.mockResolvedValue(detailedResult)
    render(<VerificationModal task={task} onClose={vi.fn()} />)

    await user.click(await screen.findByRole('button', { name: '提交检验' }))

    expect(await screen.findByText('总分：70 / 100')).toBeTruthy()
    const first = screen.getByTestId('verification-detail-1')
    expect(first.textContent).toContain('正确')
    expect(first.textContent).toContain('正确答案：A')
    const seventh = screen.getByTestId('verification-detail-7')
    expect(seventh.textContent).toContain('错误')
    expect(seventh.textContent).toContain('正确答案：C')
    const eighth = screen.getByTestId('verification-detail-8')
    expect(eighth.textContent).toContain('5 / 10 分')
    expect(eighth.textContent).toContain('需要补充边界条件')
    expect(screen.getAllByTestId(/verification-detail-/)).toHaveLength(10)
  })

  it('retains the delivery-mode result summary', async () => {
    const user = userEvent.setup()
    mockedApi.getVerification.mockResolvedValue({
      mode: 'deliver', record_id: 43,
      content: { acceptance_criteria: '提供可运行的作品' },
    })
    mockedApi.submitVerification.mockResolvedValue({
      passed: true, score: 0.8, feedback: '成果符合标准', verified: true,
    })
    render(<VerificationModal task={{ ...task, type: 'project' }} onClose={vi.fn()} />)

    await user.click(await screen.findByRole('button', { name: '提交评审' }))

    const result = await screen.findByText('✓ 检验通过')
    const summary = result.parentElement as HTMLElement
    expect(within(summary).getByText('得分：80%')).toBeTruthy()
    expect(within(summary).getByText('成果符合标准')).toBeTruthy()
    expect(within(summary).queryByText(/总分/)).toBeNull()
  })
})
