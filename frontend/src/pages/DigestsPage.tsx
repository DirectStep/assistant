import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { downloadDigestPdf, getDigest, listDigests } from '../api/digests'
import type { DigestArticle, NewsCategory } from '../types/digest'

const sectionTitles: Record<NewsCategory, string> = {
  ai: 'Искусственный интеллект',
  russian_market: 'Российский рынок',
  geopolitics: 'Геополитика',
  russia_ukraine: 'Россия — Украина',
  startups: 'Стартапы',
}

const sectionOrder = Object.keys(sectionTitles) as NewsCategory[]

function formatDate(value: string, withYear = false) {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    ...(withYear ? { year: 'numeric' } : {}),
  }).format(new Date(`${value}T12:00:00`))
}

export function DigestsPage() {
  const { date } = useParams()
  return date ? <DigestDetails date={date} /> : <DigestArchive />
}

function DigestArchive() {
  const digests = useQuery({ queryKey: ['digests'], queryFn: listDigests })

  return (
    <main className="simple-page digest-page">
      <header className="page-header">
        <div><p>Архив</p><h1>Сводки</h1></div>
      </header>
      {digests.isPending && <div className="loading-state">Загружаю…</div>}
      {digests.isError && <div className="error-banner">Не удалось загрузить сводки.</div>}
      {digests.data?.length === 0 && (
        <section className="empty-state">
          <div className="empty-glyph">≋</div>
          <h2>Сводок пока нет</h2>
          <p>Первая появится после утреннего запуска или команды /news.</p>
        </section>
      )}
      {digests.data && digests.data.length > 0 && (
        <section className="digest-list" aria-label="Архив сводок">
          {digests.data.map((digest) => (
            <Link className="digest-row" to={`/digests/${digest.date}`} key={digest.date}>
              <span>
                <strong>{formatDate(digest.date, true)}</strong>
                <small>{digest.article_count} новостей</small>
              </span>
              <span className={`digest-status ${digest.status}`}>
                {digest.status === 'completed' ? 'Готова' : 'Ошибка'}
              </span>
              <span aria-hidden="true">›</span>
            </Link>
          ))}
        </section>
      )}
    </main>
  )
}

function DigestDetails({ date }: { date: string }) {
  const digest = useQuery({ queryKey: ['digests', date], queryFn: () => getDigest(date) })
  const download = useMutation({ mutationFn: () => downloadDigestPdf(date) })

  return (
    <main className="simple-page digest-page digest-details">
      <header className="digest-detail-header">
        <Link to="/digests" className="back-link" aria-label="Вернуться к архиву">‹</Link>
        <div><p>Ежедневная сводка</p><h1>{formatDate(date, true)}</h1></div>
      </header>
      {digest.isPending && <div className="loading-state">Загружаю…</div>}
      {digest.isError && <div className="error-banner">Сводка не найдена.</div>}
      {digest.data && (
        <>
          <section className="digest-intro">
            <h2>Главное за день</h2>
            <p>{digest.data.intro || 'Краткое вступление не сформировано.'}</p>
          </section>
          {sectionOrder.map((category) => {
            const articles = digest.data.articles.filter((item) => item.category === category)
            return (
              <DigestSection
                key={category}
                title={sectionTitles[category]}
                articles={articles}
              />
            )
          })}
          {digest.data.pdf_available && (
            <button
              className="primary-button digest-download"
              type="button"
              disabled={download.isPending}
              onClick={() => download.mutate()}
            >
              {download.isPending ? 'Скачиваю…' : 'Открыть PDF'}
            </button>
          )}
          {download.isError && <div className="error-banner">Не удалось скачать PDF.</div>}
        </>
      )}
    </main>
  )
}

function DigestSection({ title, articles }: { title: string; articles: DigestArticle[] }) {
  return (
    <section className="digest-section">
      <h2>{title}</h2>
      {articles.length === 0 && <p className="digest-empty">Важных новостей не найдено.</p>}
      {articles.map((article) => (
        <article className="digest-article" key={article.url}>
          <h3>{article.title}</h3>
          <p>{article.summary}</p>
          <h4>Почему важно</h4>
          <p>{article.why_it_matters}</p>
          <a href={article.url} target="_blank" rel="noreferrer">{article.source} ↗</a>
        </article>
      ))}
    </section>
  )
}
