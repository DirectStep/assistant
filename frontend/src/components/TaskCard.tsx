import { useDraggable } from '@dnd-kit/core'

import type { Task } from '../types/task'

const dateFormatter = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' })

export function TaskCard({
  task,
  onOpen,
  draggable = true,
}: {
  task: Task
  onOpen: () => void
  draggable?: boolean
}) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, isDragging } = useDraggable({
    id: `task-${task.id}`,
    data: { taskId: task.id },
    disabled: !draggable,
  })
  const overdue = Boolean(task.status !== 'done' && task.due_at && new Date(task.due_at) < new Date())
  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={`task-card${task.importance === 'important' ? ' important' : ''}${overdue ? ' overdue' : ''}${isDragging ? ' dragging' : ''}${draggable ? '' : ' static'}`}
      onClick={onOpen}
    >
      <header>
        <button
          className="task-open-button"
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            onOpen()
          }}
        >
          <h3>{task.title}</h3>
        </button>
        {draggable && (
          <button
            ref={setActivatorNodeRef}
            className="drag-handle"
            type="button"
            aria-label={`Перетащить задачу «${task.title}»`}
            onClick={(event) => event.stopPropagation()}
            {...listeners}
            {...attributes}
          >
            <span /><span /><span />
          </button>
        )}
      </header>
      {task.description && <p>{task.description}</p>}
      <footer>
        {task.due_at && (
          <time dateTime={task.due_at}>
            {overdue ? 'Просрочено · ' : ''}{dateFormatter.format(new Date(task.due_at))}
          </time>
        )}
        {task.importance === 'important' && <span>Важно</span>}
      </footer>
    </article>
  )
}
