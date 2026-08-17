import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import { AuthProvider } from '../auth/AuthContext'
import { AuthPage } from './AuthPage'


vi.mock('../api/client', () => ({
  api: {
    me: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

function renderAuth() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<AuthPage />} />
          <Route path="/" element={<div>HOME</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

afterEach(cleanup)

describe('AuthPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.me.mockRejectedValue(new Error('no session'))
  })

  it('logs in and navigates home', async () => {
    const user = userEvent.setup()
    mockedApi.login.mockResolvedValue({
      id: 1,
      username: 'alice',
      created_at: '2026-08-17T00:00:00',
    })
    renderAuth()

    await user.type(screen.getByLabelText('用户名'), 'alice')
    await user.type(screen.getByLabelText('密码'), 'secret123')
    await user.click(screen.getByRole('button', { name: '登录账号' }))

    await waitFor(() => {
      expect(mockedApi.login).toHaveBeenCalledWith('alice', 'secret123')
    })
    expect(await screen.findByText('HOME')).toBeTruthy()
  })

  it('registers and navigates home', async () => {
    const user = userEvent.setup()
    mockedApi.register.mockResolvedValue({
      id: 2,
      username: 'bob',
      created_at: '2026-08-17T00:00:00',
    })
    renderAuth()

    await user.click(screen.getByRole('button', { name: '注册' }))
    await user.type(screen.getByLabelText('用户名'), 'bob')
    await user.type(screen.getByLabelText('密码'), 'secret123')
    await user.click(screen.getByRole('button', { name: '注册账号' }))

    await waitFor(() => {
      expect(mockedApi.register).toHaveBeenCalledWith('bob', 'secret123')
    })
    expect(await screen.findByText('HOME')).toBeTruthy()
  })

  it('shows the login error and stays on the auth page', async () => {
    const user = userEvent.setup()
    mockedApi.login.mockRejectedValue(new Error('用户名或密码错误'))
    renderAuth()

    await user.type(screen.getByLabelText('用户名'), 'alice')
    await user.type(screen.getByLabelText('密码'), 'wrongpass1')
    await user.click(screen.getByRole('button', { name: '登录账号' }))

    expect((await screen.findByRole('alert')).textContent).toBe('用户名或密码错误')
    expect(screen.queryByText('HOME')).toBeNull()
  })
})
