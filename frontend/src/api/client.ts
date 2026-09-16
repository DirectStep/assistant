import { getTelegramInitData } from '../telegram'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
  }
}

async function request(path: string, options: RequestInit): Promise<Response> {
  const headers = new Headers(options.headers)
  const initData = getTelegramInitData()
  if (initData) headers.set('Authorization', `tma ${initData}`)
  if (options.body) headers.set('Content-Type', 'application/json')

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  if (!response.ok) {
    let message = 'Не удалось выполнить запрос'
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) message = body.detail
    } catch {
      // The status code still carries enough information for the UI.
    }
    throw new ApiError(message, response.status)
  }
  return response
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await request(path, options)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function apiBlob(path: string): Promise<Blob> {
  return (await request(path, {})).blob()
}
