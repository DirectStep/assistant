export type DigestStatus = 'pending' | 'processing' | 'completed' | 'failed'

export type NewsCategory =
  | 'ai'
  | 'russian_market'
  | 'geopolitics'
  | 'russia_ukraine'
  | 'startups'

export interface DigestArchiveItem {
  date: string
  status: DigestStatus
  article_count: number
  pdf_available: boolean
  created_at: string
}

export interface DigestArticle {
  title: string
  url: string
  source: string
  category: NewsCategory
  published_at: string
  relevance_score: number
  summary: string
  why_it_matters: string
}

export interface DigestDetail {
  date: string
  status: DigestStatus
  intro: string
  pdf_available: boolean
  articles: DigestArticle[]
}
