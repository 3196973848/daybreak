import { act, cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from '../api/client'
import type { LearningSessionDTO } from '../types'
import { LearningPage } from './LearningPage'
import '../index.css'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    api: {
      getLearningSession: vi.fn(),
      startLearningSession: vi.fn(),
      sendLearningTurn: vi.fn(),
      getVerification: vi.fn(),
      submitVerification: vi.fn(),
    },
  }
})

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

const existingSession: LearningSessionDTO = {
  id: 41,
  task_id: 7,
  goal_id: 3,
  task_title: '理解 JavaScript 闭包',
  task_description: '掌握词法作用域与常见应用',
  stage: 'explain',
  covered_points: ['词法作用域', '函数返回函数'],
  weak_points: ['循环中的闭包'],
  ready_for_verification: false,
  estimated_hours_snapshot: 1.5,
  turns: [
    {
      id: 1,
      client_turn_id: 'server-opening',
      user_message: null,
      assistant_message: '先说说你对闭包的理解。',
      stage: 'diagnose',
      created_at: '2026-08-14T09:00:00Z',
    },
    {
      id: 2,
      client_turn_id: 'client-answer',
      user_message: '函数可以记住外层变量。',
      assistant_message: '很好，接下来看看它为什么能记住。',
      stage: 'explain',
      created_at: '2026-08-14T09:01:00Z',
    },
  ],
}

function renderPage(path = '/tasks/7/learn') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/tasks/:taskId/learn" element={<LearningPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('LearningPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('crypto', {
      randomUUID: vi.fn(() => '11111111-1111-4111-8111-111111111111'),
    })
    mockedApi.getLearningSession.mockResolvedValue(existingSession)
  })

  it('restores the full conversation and learning status from GET', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: '理解 JavaScript 闭包' })).toBeTruthy()
    expect(screen.getAllByText('讲解').length).toBeGreaterThan(0)
    expect(screen.getByText('1.5 小时')).toBeTruthy()
    expect(screen.getByText('词法作用域')).toBeTruthy()
    expect(screen.getByText('函数返回函数')).toBeTruthy()
    expect(screen.getByText('循环中的闭包')).toBeTruthy()
    expect(screen.getByText('先说说你对闭包的理解。')).toBeTruthy()
    expect(screen.getByText('函数可以记住外层变量。')).toBeTruthy()
    expect(screen.getByText('很好，接下来看看它为什么能记住。')).toBeTruthy()
  })

  it('starts only a missing session and announces preparation before the diagnostic arrives', async () => {
    const start = deferred<LearningSessionDTO>()
    mockedApi.getLearningSession.mockRejectedValue(new ApiError(404, '未找到'))
    mockedApi.startLearningSession.mockReturnValue(start.promise)
    renderPage()

    expect(await screen.findByText('导师正在准备诊断问题')).toBeTruthy()
    start.resolve({
      ...existingSession,
      stage: 'diagnose',
      turns: [{
        ...existingSession.turns[0],
        assistant_message: '先用一句话解释什么是词法作用域。',
      }],
    })

    expect(await screen.findByText('先用一句话解释什么是词法作用域。')).toBeTruthy()
    expect(mockedApi.startLearningSession).toHaveBeenCalledWith(7)
  })

  it('does not create a session when GET fails for a reason other than 404', async () => {
    mockedApi.getLearningSession.mockRejectedValue(new ApiError(500, '服务暂时不可用'))
    renderPage()

    expect((await screen.findByRole('alert')).textContent).toBe('服务暂时不可用')
    expect(mockedApi.startLearningSession).not.toHaveBeenCalled()
  })

  it('does not start a session when an abandoned task GET later rejects with 404', async () => {
    const user = userEvent.setup()
    const abandonedGet = deferred<LearningSessionDTO>()
    mockedApi.getLearningSession
      .mockReturnValueOnce(abandonedGet.promise)
      .mockResolvedValueOnce({
        ...existingSession,
        task_id: 8,
        task_title: '当前任务',
      })
    render(
      <MemoryRouter initialEntries={['/tasks/7/learn']}>
        <Link to="/tasks/8/learn">切换任务</Link>
        <Routes>
          <Route path="/tasks/:taskId/learn" element={<LearningPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('link', { name: '切换任务' }))
    expect(await screen.findByRole('heading', { name: '当前任务' })).toBeTruthy()
    await act(async () => {
      abandonedGet.reject(new ApiError(404, '未找到'))
      await abandonedGet.promise.catch(() => undefined)
    })

    expect(mockedApi.startLearningSession).not.toHaveBeenCalled()
  })

  it('creates one UUID and disables duplicate submission while the tutor is thinking', async () => {
    const user = userEvent.setup()
    const send = deferred<LearningSessionDTO>()
    mockedApi.sendLearningTurn.mockReturnValue(send.promise)
    renderPage()

    const textarea = await screen.findByRole('textbox', { name: '回复导师' }) as HTMLTextAreaElement
    await user.type(textarea, '它保存了定义位置的作用域。')
    await user.click(screen.getByRole('button', { name: '发送' }))

    expect(await screen.findByText('导师正在思考')).toBeTruthy()
    expect(textarea.disabled).toBe(true)
    expect((screen.getByRole('button', { name: '发送中' }) as HTMLButtonElement).disabled).toBe(true)
    await user.click(screen.getByRole('button', { name: '发送中' }))
    expect(mockedApi.sendLearningTurn).toHaveBeenCalledTimes(1)
    expect(mockedApi.sendLearningTurn).toHaveBeenCalledWith(7, {
      client_turn_id: '11111111-1111-4111-8111-111111111111',
      message: '它保存了定义位置的作用域。',
    })
    expect(crypto.randomUUID).toHaveBeenCalledTimes(1)
  })

  it('preserves the textarea and exact request body across a failed send and retry', async () => {
    const user = userEvent.setup()
    const successfulSession = {
      ...existingSession,
      turns: [
        ...existingSession.turns,
        {
          id: 3,
          client_turn_id: '11111111-1111-4111-8111-111111111111',
          user_message: '我想用一个例子继续。',
          assistant_message: '好，我们来看计数器闭包。',
          stage: 'practice' as const,
          created_at: '2026-08-14T09:02:00Z',
        },
      ],
    }
    mockedApi.sendLearningTurn
      .mockRejectedValueOnce(new Error('网络中断'))
      .mockResolvedValueOnce(successfulSession)
    renderPage()

    const textarea = await screen.findByRole('textbox', { name: '回复导师' }) as HTMLTextAreaElement
    await user.type(textarea, '我想用一个例子继续。')
    await user.click(screen.getByRole('button', { name: '发送' }))

    expect((await screen.findByRole('alert')).textContent).toBe('网络中断')
    expect(textarea.value).toBe('我想用一个例子继续。')
    expect(textarea.disabled).toBe(true)
    await user.click(screen.getByRole('button', { name: '重试' }))

    await screen.findByText('好，我们来看计数器闭包。')
    const firstBody = mockedApi.sendLearningTurn.mock.calls[0][1]
    const retryBody = mockedApi.sendLearningTurn.mock.calls[1][1]
    expect(retryBody).toEqual(firstBody)
    expect(retryBody).toEqual({
      client_turn_id: '11111111-1111-4111-8111-111111111111',
      message: '我想用一个例子继续。',
    })
    expect(crypto.randomUUID).toHaveBeenCalledTimes(1)
    expect(textarea.value).toBe('')
  })

  it.each([
    { ready: true, visible: true },
    { ready: false, visible: false },
  ])('shows the verification recommendation only when ready=$ready', async ({ ready, visible }) => {
    mockedApi.getLearningSession.mockResolvedValue({
      ...existingSession,
      stage: ready ? 'ready' : 'practice',
      ready_for_verification: ready,
    })
    renderPage()

    await screen.findByRole('heading', { name: '理解 JavaScript 闭包' })
    expect(Boolean(screen.queryByText('建议开始检验'))).toBe(visible)
  })

  it('renders Markdown structure while keeping script markup inert text', async () => {
    mockedApi.getLearningSession.mockResolvedValue({
      ...existingSession,
      turns: [{
        ...existingSession.turns[0],
        assistant_message: [
          '这是一个段落。',
          '',
          '- 第一项',
          '- 第二项',
          '',
          '```js',
          'const answer = 42',
          '```',
          '',
          '`<script>alert(1)</script>`',
          '',
          '<script>alert(1)</script>',
        ].join('\n'),
      }],
    })
    const { container } = renderPage()

    const paragraph = await screen.findByText('这是一个段落。')
    expect(paragraph.tagName).toBe('P')
    const markdown = container.querySelector('.learning-markdown') as HTMLElement
    const list = within(markdown).getByRole('list')
    expect(within(list).getAllByRole('listitem')).toHaveLength(2)
    expect(within(markdown).getByText('const answer = 42').tagName).toBe('CODE')
    expect(within(markdown).getByText('<script>alert(1)</script>').tagName).toBe('CODE')
    expect(container.querySelector('script')).toBeNull()
  })

  it('uses a two-column learning layout with status before chat in DOM order', async () => {
    const { container } = renderPage()

    await screen.findByRole('heading', { name: '理解 JavaScript 闭包' })
    const layout = container.querySelector('.learning-layout') as HTMLElement
    const status = container.querySelector('.learning-status-card') as HTMLElement
    const chat = container.querySelector('.learning-chat') as HTMLElement
    expect(layout).toBeTruthy()
    expect(getComputedStyle(layout).display).toBe('grid')
    expect(status).toBeTruthy()
    expect(chat).toBeTruthy()
    expect(status.compareDocumentPosition(chat) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('opens the verification modal and returns to daily tasks', async () => {
    const user = userEvent.setup()
    mockedApi.getVerification.mockResolvedValue({
      mode: 'test',
      record_id: 42,
      content: { questions: [] },
    })
    renderPage()

    await user.click(await screen.findByRole('button', { name: '开始检验' }))

    expect(await screen.findByText('检验 · 理解 JavaScript 闭包')).toBeTruthy()
    expect(screen.getByRole('link', { name: '返回' }).getAttribute('href')).toBe('/goals/3/daily')
  })

  it('marks verification passed and disables the action', async () => {
    const user = userEvent.setup()
    mockedApi.getVerification.mockResolvedValue({
      mode: 'test',
      record_id: 42,
      content: { questions: [] },
    })
    mockedApi.submitVerification.mockResolvedValue({
      passed: true,
      score: 1,
      feedback: '通过',
      verified: true,
    })
    renderPage()

    await user.click(await screen.findByRole('button', { name: '开始检验' }))
    await user.click(await screen.findByRole('button', { name: '提交检验' }))

    const done = await screen.findByRole('button', { name: '检验已通过' })
    expect((done as HTMLButtonElement).disabled).toBe(true)
  })

  it('does not claim completion after a failed verification', async () => {
    const user = userEvent.setup()
    mockedApi.getVerification.mockResolvedValue({
      mode: 'test',
      record_id: 42,
      content: { questions: [] },
    })
    mockedApi.submitVerification.mockResolvedValue({
      passed: false,
      score: 0.4,
      feedback: '未通过',
      verified: false,
    })
    renderPage()

    await user.click(await screen.findByRole('button', { name: '开始检验' }))
    await user.click(await screen.findByRole('button', { name: '提交检验' }))

    expect(await screen.findByText('✗ 未通过')).toBeTruthy()
    expect(screen.queryByText('检验已通过')).toBeNull()
    expect(screen.getByRole('button', { name: '开始检验' })).toBeTruthy()
  })
})
