import type { Task, TaskInput, TaskStatus } from '../types/task'
import { apiRequest } from './client'

export const getTasks = () => apiRequest<Task[]>('/tasks')
export const createTask = (data: TaskInput) =>
  apiRequest<Task>('/tasks', { method: 'POST', body: JSON.stringify(data) })
export const updateTask = (id: number, data: Partial<TaskInput>) =>
  apiRequest<Task>(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
export const moveTask = (id: number, status: TaskStatus) =>
  apiRequest<Task>(`/tasks/${id}/move`, {
    method: 'POST',
    body: JSON.stringify({ status }),
  })
export const completeTask = (id: number) =>
  apiRequest<Task>(`/tasks/${id}/complete`, { method: 'POST' })
export const deleteTask = (id: number) =>
  apiRequest<void>(`/tasks/${id}`, { method: 'DELETE' })
