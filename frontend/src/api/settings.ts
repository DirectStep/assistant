import type { UserSettings } from '../types/task'
import { apiRequest } from './client'

export const getSettings = () => apiRequest<UserSettings>('/settings')
export const updateSettings = (data: Partial<UserSettings>) =>
  apiRequest<UserSettings>('/settings', { method: 'PATCH', body: JSON.stringify(data) })
