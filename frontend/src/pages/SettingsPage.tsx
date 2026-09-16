import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { getSettings, updateSettings } from '../api/settings'

const topics = [
  ['ai', 'Искусственный интеллект'],
  ['russian_market', 'Российский рынок'],
  ['geopolitics', 'Геополитика'],
  ['russia_ukraine', 'Россия — Украина'],
  ['startups', 'Стартапы'],
] as const

export function SettingsPage() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['settings'], queryFn: getSettings })
  const [draft, setDraft] = useState<{
    time?: string
    timezone?: string
    topics?: string[]
    count?: number
  }>({})
  const mutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  })

  const time = draft.time ?? query.data?.daily_digest_time.slice(0, 5) ?? '08:30'
  const timezone = draft.timezone ?? query.data?.timezone ?? 'Europe/Moscow'
  const selectedTopics = draft.topics ?? query.data?.news_topics ?? []
  const count = draft.count ?? query.data?.news_max_articles ?? 10

  return (
    <main className="simple-page settings-page">
      <header className="page-header"><div><p>Личное расписание</p><h1>Настройки</h1></div></header>
      {query.isLoading ? <div className="loading-state">Загружаю настройки…</div> : query.isError ? (
        <div className="empty-state" role="alert">
          <h2>Настройки не загрузились</h2>
          <p>Проверь соединение и попробуй ещё раз.</p>
          <button className="quiet-button" type="button" onClick={() => void query.refetch()}>Повторить</button>
        </div>
      ) : (
        <form onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate({
            daily_digest_time: `${time}:00`,
            timezone,
            news_topics: selectedTopics,
            news_max_articles: count,
          })
        }}>
          <section className="settings-section">
            <h2>Утренняя сводка</h2>
            <div className="form-grid">
              <label>Время<input type="time" value={time} onChange={(event) => setDraft((current) => ({ ...current, time: event.target.value }))} required /></label>
              <label>Часовой пояс<input value={timezone} onChange={(event) => setDraft((current) => ({ ...current, timezone: event.target.value }))} required /></label>
            </div>
          </section>
          <section className="settings-section">
            <h2>Новости</h2>
            <div className="topic-list">
              {topics.map(([value, label]) => (
                <label key={value}>
                  <span>{label}</span>
                  <input
                    type="checkbox"
                    checked={selectedTopics.includes(value)}
                    onChange={(event) => setDraft((current) => ({
                      ...current,
                      topics: event.target.checked
                        ? [...selectedTopics, value]
                        : selectedTopics.filter((item) => item !== value),
                    }))}
                  />
                </label>
              ))}
            </div>
            <label className="range-label">
              <span>Количество новостей <strong>{count}</strong></span>
              <input type="range" min="5" max="20" value={count} onChange={(event) => setDraft((current) => ({ ...current, count: Number(event.target.value) }))} />
            </label>
          </section>
          {mutation.error && <div className="error-banner">Настройки не сохранены. Проверь значения.</div>}
          <button className="primary-button settings-save" type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Сохраняю…' : 'Сохранить настройки'}
          </button>
        </form>
      )}
    </main>
  )
}
