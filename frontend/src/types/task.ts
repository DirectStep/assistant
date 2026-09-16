export type TaskStatus = 'inbox' | 'today' | 'week' | 'later' | 'done'
export type TaskImportance = 'normal' | 'important'
export type TaskSource = 'text' | 'forward' | 'voice' | 'webapp'

export interface Task {
  id: number
  telegram_user_id: number
  title: string
  description: string | null
  source_type: TaskSource
  source_text: string | null
  source_metadata: Record<string, unknown> | null
  status: TaskStatus
  importance: TaskImportance
  due_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface TaskInput {
  title: string
  description?: string | null
  status: TaskStatus
  importance: TaskImportance
  due_at?: string | null
}

export interface UserSettings {
  telegram_user_id: number
  daily_digest_time: string
  timezone: string
  news_topics: string[]
  news_max_articles: number
}
