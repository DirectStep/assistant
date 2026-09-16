import { useEffect, useRef, useState } from 'react'

import type { Task, TaskImportance, TaskInput, TaskStatus } from '../types/task'

const statuses: { value: TaskStatus; label: string }[] = [
  { value: 'inbox', label: 'Входящие' },
  { value: 'today', label: 'Сегодня' },
  { value: 'week', label: 'На неделе' },
  { value: 'later', label: 'Позже' },
  { value: 'done', label: 'Готово' },
]

function toInputDate(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export function TaskSheet({
  task,
  busy,
  error,
  onClose,
  onSave,
  onDelete,
  onComplete,
}: {
  task: Task | null
  busy: boolean
  error: boolean
  onClose: () => void
  onSave: (data: TaskInput) => void
  onDelete: () => void
  onComplete: () => void
}) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [title, setTitle] = useState(task?.title ?? '')
  const [description, setDescription] = useState(task?.description ?? '')
  const [dueAt, setDueAt] = useState(toInputDate(task?.due_at ?? null))
  const [status, setStatus] = useState<TaskStatus>(task?.status ?? 'inbox')
  const [importance, setImportance] = useState<TaskImportance>(task?.importance ?? 'normal')

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    dialog.showModal()
    return () => dialog.close()
  }, [])

  return (
    <dialog
      ref={dialogRef}
      className="task-sheet"
      aria-labelledby="task-sheet-title"
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
    >
        <div className="sheet-handle" />
        <header>
          <h2 id="task-sheet-title">{task ? 'Задача' : 'Новая задача'}</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Закрыть">×</button>
        </header>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            if (!title.trim()) return
            onSave({
              title: title.trim(),
              description: description.trim() || null,
              due_at: dueAt ? new Date(dueAt).toISOString() : null,
              status,
              importance,
            })
          }}
        >
          <label>
            Название
            <input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} maxLength={500} required />
          </label>
          <label>
            Описание
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} />
          </label>
          <div className="form-grid">
            <label>
              Дедлайн
              <input type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} />
            </label>
            <label>
              Статус
              <select value={status} onChange={(event) => setStatus(event.target.value as TaskStatus)}>
                {statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
          </div>
          <label className="importance-toggle">
            <input
              type="checkbox"
              checked={importance === 'important'}
              onChange={(event) => setImportance(event.target.checked ? 'important' : 'normal')}
            />
            <span>Важная задача</span>
          </label>
          {error && <div className="error-banner" role="alert">Не удалось сохранить задачу. Проверь соединение.</div>}
          <div className="sheet-actions">
            {task && <button className="danger-button" type="button" onClick={onDelete} disabled={busy}>Удалить</button>}
            {task && task.status !== 'done' && <button className="quiet-button" type="button" onClick={onComplete} disabled={busy}>Завершить</button>}
            <button className="primary-button" type="submit" disabled={busy || !title.trim()}>{busy ? 'Сохраняю…' : 'Сохранить'}</button>
          </div>
        </form>
    </dialog>
  )
}
