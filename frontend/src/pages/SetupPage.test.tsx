import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import { SetupPage } from './SetupPage'


vi.mock('../api/client', () => ({
  api: {
    getSettings: vi.fn(),
    saveSettings: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

function renderSetup() {
  return render(
    <MemoryRouter initialEntries={['/setup']}>
      <Routes>
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/" element={<div>HOME</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(cleanup)

describe('SetupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.getSettings.mockResolvedValue({
      configured: false,
      provider: 'deepseek',
      providers: [
        { id: 'deepseek', name: 'DeepSeek', requires_key: true, models: ['deepseek-chat'] },
        { id: 'ollama', name: 'Ollama（本地）', requires_key: false, models: ['qwen2.5'] },
      ],
      model: 'deepseek-chat',
      models: ['deepseek-chat'],
      requires_key: true,
    })
  })

  it('saves an ollama provider without requiring an API key', async () => {
    const user = userEvent.setup()
    mockedApi.saveSettings.mockResolvedValue({
      configured: true,
      provider: 'ollama',
      providers: [],
      model: 'qwen2.5',
      models: ['qwen2.5'],
      requires_key: false,
    })
    renderSetup()

    await user.click(await screen.findByRole('button', { name: /Ollama/ }))
    expect(screen.queryByLabelText('API Key')).toBeNull()
    await user.click(screen.getByRole('button', { name: '保存并开始' }))

    await waitFor(() => {
      expect(mockedApi.saveSettings).toHaveBeenCalledWith({
        provider: 'ollama',
        api_key: undefined,
        base_url: undefined,
        model: 'qwen2.5',
      })
    })
    expect(await screen.findByText('HOME')).toBeTruthy()
  })

  it('requires an API key for providers that need one', async () => {
    const user = userEvent.setup()
    renderSetup()

    await user.click(await screen.findByRole('button', { name: '保存并开始' }))

    expect((await screen.findByRole('alert')).textContent).toBe('请填写 API Key')
    expect(mockedApi.saveSettings).not.toHaveBeenCalled()
  })
})
