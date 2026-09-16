import { useDroppable } from '@dnd-kit/core'

import type { Task, TaskStatus } from '../types/task'
import { TaskCard } from './TaskCard'

export function KanbanColumn({
  status,
  title,
  tasks,
  onOpen,
}: {
  status: TaskStatus
  title: string
  tasks: Task[]
  onOpen: (task: Task) => void
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status })
  return (
    <section ref={setNodeRef} className={`kanban-column${isOver ? ' is-over' : ''}`}>
      <header><h2>{title}</h2><span>{tasks.length}</span></header>
      <div className="task-list">
        {tasks.map((task) => <TaskCard key={task.id} task={task} onOpen={() => onOpen(task)} />)}
        {tasks.length === 0 && <p className="column-empty">Перетащи задачу сюда</p>}
      </div>
    </section>
  )
}
