import {
  createContext, useCallback, useContext, useEffect, useState,
} from 'react'
import type { ReactNode } from 'react'

import { api } from '../api/client'
import type { UserDTO } from '../types'


interface AuthState {
  user: UserDTO | null
  loading: boolean
  login: (username: string, password: string) => Promise<UserDTO>
  register: (username: string, password: string) => Promise<UserDTO>
  logout: () => Promise<void>
}

const STUB: AuthState = {
  user: null,
  loading: false,
  login: async () => { throw new Error('认证服务不可用') },
  register: async () => { throw new Error('认证服务不可用') },
  logout: async () => undefined,
}

const AuthContext = createContext<AuthState>(STUB)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserDTO | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    api.me()
      .then((me) => { if (active) setUser(me) })
      .catch(() => { if (active) setUser(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => {
      active = false
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const me = await api.login(username, password)
    setUser(me)
    return me
  }, [])

  const register = useCallback(async (username: string, password: string) => {
    const me = await api.register(username, password)
    setUser(me)
    return me
  }, [])

  const logout = useCallback(async () => {
    await api.logout()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  return useContext(AuthContext)
}
